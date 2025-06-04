# main.py (for Google Cloud Function deployment)
import functions_framework
import json
import os
import logging
import sys 
import pathlib 
import io 
import csv 
import time 

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from agent_runner import run_lead_generation_process # This is the key import
    from config import Config, SJ_MORSE_PROFILE 
    from output_manager import CSV_EXPORT_HEADER 
except ImportError as e:
    logging.basicConfig(level="DEBUG") 
    initial_logger = logging.getLogger(__name__) 
    initial_logger.critical(f"CRITICAL IMPORT ERROR in main.py (GCP Handler): {e}. Current sys.path: {sys.path}", exc_info=True)
    raise 

logger = logging.getLogger(__name__)

@functions_framework.http
def sj_morse_lead_generator(request):
    expected_api_key = os.getenv("MY_SHARED_API_KEY") 
    received_api_key = request.headers.get("X-Api-Key")

    if expected_api_key:
        if not received_api_key:
            logger.warning("Missing API key in request for sj_morse_lead_generator.")
            return (json.dumps({"error": "API key required"}), 401, {"Content-Type": "application/json"})
        if received_api_key != expected_api_key:
            logger.warning("Unauthorized API key attempt for sj_morse_lead_generator.")
            return (json.dumps({"error": "Unauthorized"}), 401, {"Content-Type": "application/json"})
    
    logger.info(f"Cloud Function 'sj_morse_lead_generator' triggered. Request method: {request.method}")
    
    if request.method == 'POST':
        try:
            # --- MODIFIED: Parse request body for selected segments ---
            user_selected_segments = None
            content_type = request.headers.get('Content-Type', '').lower()

            if 'application/json' in content_type:
                request_json = request.get_json(silent=True)
                if request_json and "segments_to_run" in request_json:
                    segments_from_req = request_json["segments_to_run"]
                    if isinstance(segments_from_req, list) and all(isinstance(s, str) for s in segments_from_req):
                        user_selected_segments = segments_from_req
                        logger.info(f"User selected segments via JSON body: {user_selected_segments}")
                    else:
                        logger.warning("'segments_to_run' in JSON body was not a list of strings.")
                        # Optionally return a 400 error here if strict input validation is desired
                        # return (json.dumps({"error": "'segments_to_run' must be a list of strings"}), 400, {"Content-Type": "application/json"})
            
            if user_selected_segments is None:
                 logger.info("No 'segments_to_run' provided in JSON body or body not JSON; will process all configured segments.")
            # --- END MODIFICATION ---

            logger.info(f"Calling run_lead_generation_process from agent_runner (selected_segments: {user_selected_segments})...")
            # MODIFIED: Pass user_selected_segments
            results = run_lead_generation_process(selected_segment_names=user_selected_segments) 

            if isinstance(results, dict) and "error" in results:
                logger.error(f"Lead generation process returned an error: {results}")
                return (json.dumps(results), 500, {"Content-Type": "application/json"})

            processed_count = len(results.get("processed_companies", [])) if isinstance(results, dict) and "processed_companies" in results else \
                              len(results) if isinstance(results, list) else 'unknown amount of'

            logger.info(f"Lead generation process completed. Found {processed_count} entries.")

            # If run_lead_generation_process now returns a dict like {"message": ..., "processed_companies": [...]},
            # we need to extract the actual list of companies for CSV/JSON output.
            actual_company_list = []
            if isinstance(results, dict) and "processed_companies" in results:
                actual_company_list = results["processed_companies"]
            elif isinstance(results, list):
                actual_company_list = results
            else: # Should not happen if run_lead_generation_process is correct
                logger.error(f"Unexpected result structure from run_lead_generation_process: {type(results)}")
                return (json.dumps({"error": "Internal error: Unexpected result structure from core process"}), 500, {"Content-Type": "application/json"})


            requested_format = request.args.get('format', 'json').lower()
            logger.info(f"Requested output format: {requested_format}")

            if requested_format == 'csv' and isinstance(actual_company_list, list) and actual_company_list:
                try:
                    string_io = io.StringIO()
                    writer = csv.DictWriter(string_io, fieldnames=CSV_EXPORT_HEADER, extrasaction='ignore')
                    writer.writeheader()
                    rows_to_write = []
                    today_date_for_csv = time.strftime("%Y-%m-%d") 
                    for company_info in actual_company_list:
                        if not isinstance(company_info, dict): continue
                        csv_row = {
                            'Company Name': company_info.get('name', 'N/A'),
                            'Website': company_info.get('website', 'N/A'),
                            'Potential Pain Points': company_info.get('pain_points', ''),
                            'Contact Email': company_info.get('contact_email', ''),
                            'Source URL': company_info.get('source_url', 'N/A'),
                            'Date Added': company_info.get('date_added', today_date_for_csv),
                            'Is Duplicate': str(company_info.get('is_duplicate_in_batch', False)),
                            'Lead Category': company_info.get('category', 'Unknown') 
                        }
                        rows_to_write.append(csv_row)
                    writer.writerows(rows_to_write)
                    csv_output = string_io.getvalue()
                    string_io.close()
                    response_headers = {
                        'Content-Type': 'text/csv; charset=utf-8',
                        'Content-Disposition': 'attachment; filename="sj_morse_leads.csv"'
                    }
                    logger.info(f"Successfully generated CSV output with {len(rows_to_write)} rows.")
                    return (csv_output, 200, response_headers)
                except Exception as e_csv:
                    logger.error(f"Error generating CSV output: {e_csv}", exc_info=True)
                    return (json.dumps({"error": "Failed to generate CSV output", "details": str(e_csv), "data_preview": actual_company_list[:2] if isinstance(actual_company_list, list) else None}), 500, {"Content-Type": "application/json"})
            
            logger.info(f"Returning JSON output with {len(actual_company_list) if isinstance(actual_company_list, list) else '0'} entries.")
            # Return the full result if it was a message dict, or the list of companies for JSON.
            # If specific segments were requested and none processed, results might be a message dict.
            if isinstance(results, dict) and "message" in results and "processed_companies" in results:
                 # Return the message dict if it indicates something like "no valid segments processed"
                 return (json.dumps(results), 200, {"Content-Type": "application/json"})

            return (json.dumps(actual_company_list), 200, {"Content-Type": "application/json"})

        except Exception as e:
            logger.error(f"Unhandled exception in sj_morse_lead_generator: {e}", exc_info=True)
            return (json.dumps({"error": "Internal server error", "details": str(e)}), 500, {"Content-Type": "application/json"})
    else:
        logger.warning(f"Unsupported HTTP method: {request.method} for sj_morse_lead_generator. Use POST.")
        return (json.dumps({"error": "Method not allowed. Use POST."}), 405, {"Content-Type": "application/json"})
