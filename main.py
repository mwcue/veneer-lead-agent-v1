# main.py (for Google Cloud Function deployment)
import functions_framework
import json
import os
import logging
import sys
import pathlib
import io # <<<<<<<<<<<< ADD THIS IMPORT
import csv # <<<<<<<<<<<< ADD THIS IMPORT
import time # For 'Date Added' if not in results

# --- Add current directory to sys.path ---
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from agent_runner import run_lead_generation_process
    from config import Config, SJ_MORSE_PROFILE # SJ_MORSE_PROFILE needed if constructing CSV row data here.
    from output_manager import CSV_EXPORT_HEADER # <<<<<<<<<<<< ADD THIS IMPORT
except ImportError as e:
    logging.basicConfig(level="DEBUG")
    initial_logger = logging.getLogger(__name__)
    initial_logger.critical(f"CRITICAL IMPORT ERROR in main.py (GCP Handler): {e}. Current sys.path: {sys.path}", exc_info=True)
    raise

logger = logging.getLogger(__name__)

@functions_framework.http
def sj_morse_lead_generator(request): # 'request' is a Flask request object
    """HTTP Cloud Function to trigger SJ Morse lead generation."""
    
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
            logger.info("Calling run_lead_generation_process from agent_runner...")
            results = run_lead_generation_process() 

            if isinstance(results, dict) and "error" in results:
                logger.error(f"Lead generation process returned an error: {results}")
                return (json.dumps(results), 500, {"Content-Type": "application/json"})

            processed_count = len(results) if isinstance(results, list) else 'unknown amount of'
            logger.info(f"Lead generation process completed. Found {processed_count} entries.")

            # --- START: CSV Format Handling ---
            requested_format = request.args.get('format', 'json').lower() # Check for ?format=csv
            logger.info(f"Requested output format: {requested_format}")

            if requested_format == 'csv' and isinstance(results, list) and results:
                try:
                    string_io = io.StringIO()
                    # Use the imported CSV_EXPORT_HEADER
                    writer = csv.DictWriter(string_io, fieldnames=CSV_EXPORT_HEADER, extrasaction='ignore')
                    writer.writeheader()

                    rows_to_write = []
                    today_date_for_csv = time.strftime("%Y-%m-%d") # Generate current date for 'Date Added'

                    for company_info in results:
                        if not isinstance(company_info, dict):
                            logger.warning(f"Skipping non-dict item in results for CSV: {company_info}")
                            continue
                        
                        # Prepare a dictionary that maps our result keys to the CSV_EXPORT_HEADER keys
                        # Ensure all keys in CSV_EXPORT_HEADER are present, defaulting if necessary.
                        csv_row = {
                            'Company Name': company_info.get('name', 'N/A'),
                            'Website': company_info.get('website', 'N/A'),
                            'Potential Pain Points': company_info.get('pain_points', ''),
                            'Contact Email': company_info.get('contact_email', ''),
                            'Source URL': company_info.get('source_url', 'N/A'),
                            'Date Added': company_info.get('date_added', today_date_for_csv), # Use if present, else today
                            'Is Duplicate': str(company_info.get('is_duplicate_in_batch', False)), # Not really applicable for API response context
                            'Lead Category': company_info.get('category', 'Unknown') # This is segment_name
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
                    # Fallback to JSON if CSV generation fails
                    return (json.dumps({"error": "Failed to generate CSV output", "details": str(e_csv), "data_preview": results[:2]}), 500, {"Content-Type": "application/json"})
            
            # Default to JSON output
            logger.info(f"Returning JSON output with {processed_count} entries.")
            return (json.dumps(results), 200, {"Content-Type": "application/json"})
            # --- END: CSV Format Handling ---

        except Exception as e:
            logger.error(f"Unhandled exception in sj_morse_lead_generator: {e}", exc_info=True)
            return (json.dumps({"error": "Internal server error", "details": str(e)}), 500, {"Content-Type": "application/json"})
    else:
        logger.warning(f"Unsupported HTTP method: {request.method} for sj_morse_lead_generator. Use POST.")
        return (json.dumps({"error": "Method not allowed. Use POST."}), 405, {"Content-Type": "application/json"})
