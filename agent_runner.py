# agent_runner.py
import time
import logging
import json
from dotenv import load_dotenv

from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
from config import Config, SJ_MORSE_PROFILE
from tasks import create_search_tasks, create_extraction_task
from utils.logging_utils import get_logger, ErrorCollection
from agents import initialize_agents

# --- Global Initializations (Keep as is) ---
Config.configure_logging()
logger = get_logger(__name__)
load_dotenv()
tools = {}
initial_error_collector = ErrorCollection()
try:
    logger.debug("agent_runner.py: Attempting to import tools...")
    from tools.scraper_tools import generic_scraper_tool
    from tools.unified_email_finder import unified_email_finder_tool
    from tools.llm_tools import analyze_pain_points_tool
    from tools.search_tools import web_search_tool
    logger.debug("agent_runner.py: Tools imported.")
    tools = {
        'web_search': web_search_tool,
        'generic_scraper': generic_scraper_tool,
        'email_finder': unified_email_finder_tool,
        'pain_point_analyzer': analyze_pain_points_tool
    }
    logger.info("agent_runner.py: Global tools dictionary initialized.")
    if web_search_tool is None:
        initial_error_collector.add("Tool Initialization", ValueError("Web Search Tool failed to initialize in agent_runner"), fatal=True)
    else:
        logger.info("agent_runner.py: Web Search Tool confirmed.")
    logger.debug("agent_runner.py: Validating config...")
    missing_keys = Config.validate()
    if missing_keys:
        initial_error_collector.add("Configuration", ValueError(f"Missing required environment variables: {', '.join(missing_keys)}"), fatal=True)
    else:
        logger.info("agent_runner.py: Config validation passed (required keys check).")
    logger.info(f"agent_runner.py: LLM_PROVIDER set to: {Config.LLM_PROVIDER}")
    if Config.LLM_PROVIDER == "openai":
        logger.info(f"agent_runner.py: OPENAI_API_KEY presence: {'Yes' if Config.OPENAI_API_KEY else 'No'}")
    logger.info(f"agent_runner.py: SERPER_API_KEY presence: {'Yes' if Config.SERPER_API_KEY else 'No'}")
    if initial_error_collector.has_fatal_errors():
        logger.critical(f"Fatal errors during initial setup of agent_runner.py: {initial_error_collector.get_summary()}")
        raise RuntimeError(f"Fatal initial setup error in agent_runner.py: {initial_error_collector.get_summary()}")
    else:
        logger.info("agent_runner.py: Initial global setup checks passed successfully.")
except ImportError as e_imp:
    logger.critical(f"Fatal ImportError during agent_runner.py global setup: {e_imp}", exc_info=True)
    raise
except Exception as e_gen:
    logger.critical(f"Fatal Exception during agent_runner.py global setup: {e_gen}", exc_info=True)
    raise
# --- End Global Initializations ---


# --- Main Process Function ---
# MODIFIED: Added selected_segment_names parameter
def run_lead_generation_process(selected_segment_names: list = None):
    """
    Runs the lead generation process for the configured client (SJ Morse).
    If selected_segment_names is provided, only processes those segments.
    Otherwise, processes all target segments defined in SJ_MORSE_PROFILE.
    Returns a list of processed company data dictionaries.
    """
    run_error_collector = ErrorCollection()
    client_name = SJ_MORSE_PROFILE.get("CLIENT_NAME", "Our Client")
    logger.info(f"\n--- Starting Lead Generation Process within agent_runner for Client: {client_name} ---")
    if selected_segment_names:
        logger.info(f"Processing user-selected segments: {selected_segment_names}")
    else:
        logger.info("No specific segments selected by user; processing all configured target segments.")

    all_processed_companies = []
    processed_websites_this_run = set()

    try:
        agents = initialize_agents(tools, SJ_MORSE_PROFILE)
        logger.info(f"Agents initialized successfully for run. Available agents: {list(agents.keys())}")
    except Exception as e:
        run_error_collector.add("Agent Initialization for Run", e, fatal=True)
        logger.error(f"Fatal error during agent initialization for this run: {e}", exc_info=True)
        return {"error": "Agent initialization failed", "details": str(e), "processed_companies": []}

    if 'research' not in agents or not agents['research']:
        logger.error("Critical: Research agent not found after initialization. Aborting process.")
        return {"error": "Research agent missing", "processed_companies": []}

    # --- Determine which segments to process ---
    segments_to_actually_process = []
    all_defined_segment_configs = SJ_MORSE_PROFILE.get("TARGET_SEGMENTS", [])

    if selected_segment_names and isinstance(selected_segment_names, list):
        for name_to_find in selected_segment_names:
            found = False
            for config in all_defined_segment_configs:
                if config.get("SEGMENT_NAME") == name_to_find:
                    segments_to_actually_process.append(config)
                    found = True
                    break
            if not found:
                logger.warning(f"Requested segment '{name_to_find}' not found in SJ_MORSE_PROFILE. It will be skipped.")
        if not segments_to_actually_process:
            logger.warning("No valid segments selected by user, or none of the selected segments were found in configuration. No segments will be processed.")
            # Return early if no valid segments are to be processed based on user selection
            return {"message": "No valid segments selected or found for processing.", "selected_segments": selected_segment_names, "processed_companies": []}
    else: # If no specific segments selected, or selection was invalid type, process all
        segments_to_actually_process = all_defined_segment_configs
        if not selected_segment_names and selected_segment_names is not None: # e.g., empty list was passed
             logger.warning("An empty list of segments was selected by user. Processing all segments as a fallback.")


    if not segments_to_actually_process:
        logger.warning("No segments configured or selected for processing. Process will now end.")
        return {"message": "No segments to process.", "processed_companies": []}
    
    logger.info(f"Will process the following segments: {[s.get('SEGMENT_NAME') for s in segments_to_actually_process]}")
    # --- End segment determination ---

    for segment_config in segments_to_actually_process: # MODIFIED: Loop over filtered list
        segment_name = segment_config.get("SEGMENT_NAME")
        # (Rest of the loop logic for search, extraction, analysis remains the same as before)
        # ...
        logger.info(f"\n>>> Processing Segment: {segment_name} <<<")

        logger.info(f"  Creating search tasks for segment: {segment_name}...")
        search_tasks = create_search_tasks(agents['research'], segment_config)
        
        if not search_tasks:
            logger.error(f"  Failed to create search tasks for segment: {segment_name}. Skipping segment.")
            run_error_collector.add(f"Search Task Creation - {segment_name}", ValueError("Task creation failed"))
            continue
            
        logger.info(f"  Performing search for segment: {segment_name}...")
        url_list = perform_search(agents, search_tasks)

        if not url_list:
            logger.warning(f"  No URLs found by Research Agent for segment: {segment_name}.")
            continue

        logger.info(f"  Found {len(url_list)} URLs for {segment_name}. Processing up to {Config.MAX_URLS_TO_PROCESS} URLs.")
        urls_to_process = url_list[:Config.MAX_URLS_TO_PROCESS]

        for i, target_url in enumerate(urls_to_process):
            logger.info(f"\n    Processing URL {i+1}/{len(urls_to_process)} for {segment_name}: {target_url}")

            logger.debug(f"      Creating extraction task for URL: {target_url}...")
            extraction_task = create_extraction_task(target_url, agents['research'])
            
            if not extraction_task:
                logger.error(f"      Failed to create extraction task for {target_url}. Skipping URL.")
                run_error_collector.add(f"Extraction Task Creation - {target_url}", ValueError("Task creation failed"))
                continue

            logger.debug(f"      Extracting companies from URL: {target_url}...")
            extracted_company_data = extract_companies_from_url(target_url, agents, extraction_task)

            if not extracted_company_data:
                logger.info(f"      No companies extracted from {target_url} for segment {segment_name}.")
                continue

            logger.info(f"      Found {len(extracted_company_data)} potential companies from {target_url}. Analyzing...")
            for company_dict in extracted_company_data:
                company_name = company_dict.get('name')
                company_website = company_dict.get('website')

                if not company_name or not company_website:
                    logger.warning(f"        Skipping entry with missing name/website: {company_dict}")
                    continue

                normalized_website = company_website.strip().lower().replace('www.','').rstrip('/')
                if normalized_website in processed_websites_this_run:
                    logger.info(f"        Skipping already processed website in this run: '{company_name}' ({company_website})")
                    continue
                
                if company_name.lower() in Config.GENERIC_COMPANY_NAMES:
                    logger.info(f"        Skipping generic company name: '{company_name}'")
                    continue

                processed_websites_this_run.add(normalized_website)
                logger.info(f"        Analyzing '{company_name}' ({company_website}) for segment: {segment_name}")

                company_analysis_data = analyze_company(
                    company_name=company_name,
                    company_website=company_website,
                    agents=agents, 
                    segment_config=segment_config,
                    client_profile=SJ_MORSE_PROFILE
                )

                if company_analysis_data: 
                    company_analysis_data["source_url"] = target_url 
                    company_analysis_data["segment_name_internal"] = segment_name 
                    company_analysis_data["category"] = segment_name 
                    all_processed_companies.append(company_analysis_data)
                    pain_points_snippet = str(company_analysis_data.get('pain_points', 'N/A'))[:70]
                    logger.info(f"        Successfully analyzed '{company_name}'. Email: {company_analysis_data.get('contact_email', 'N/A')}, Pain Points: {pain_points_snippet}...")
                else:
                    logger.error(f"        Analysis for '{company_name}' (segment: {segment_name}) unexpectedly returned None or falsy value.")
                    all_processed_companies.append({
                        "name": company_name, "website": company_website,
                        "pain_points": "Critical: Analysis function returned no data", "contact_email": "",
                        "source_url": target_url, "category": segment_name,
                        "segment_name_internal": segment_name
                    })
                
                sleep_duration = Config.API_RETRY_DELAY / 2 if Config.API_RETRY_DELAY > 0 else 0.5
                if sleep_duration > 0: 
                    logger.debug(f"        Sleeping for {sleep_duration:.2f} seconds...")
                    time.sleep(sleep_duration)
        logger.info(f"  --- Finished processing URLs for segment: {segment_name} ---")
    logger.info("--- Finished Processing All Segments ---")

    if run_error_collector.has_errors():
        logger.warning("\n--- Errors Occurred During This Lead Generation Run ---")
        logger.warning(run_error_collector.get_summary())
        logger.warning("--- End of Run Error Summary ---")
    
    return all_processed_companies


# --- Local Execution Block (for direct testing of agent_runner.py) ---
if __name__ == "__main__":
    logger.info("<<<<< agent_runner.py executed directly >>>>>")
    
    run_start_time = time.time()
    # Example of calling with selected segments for local testing:
    # test_segments = ["General Contractors & Design-Build Firms", "Architectural Millwork & Woodworking Shops"]
    # processed_leads = run_lead_generation_process(selected_segment_names=test_segments)
    
    # Call without selected segments to run all (default behavior)
    processed_leads = run_lead_generation_process()
    run_end_time = time.time()

    logger.info(f"Total lead generation process completed in {run_end_time - run_start_time:.2f} seconds.")

    # (Rest of the if __name__ == "__main__": block for logging and CSV writing remains the same)
    # ...
    if isinstance(processed_leads, dict) and "error" in processed_leads:
        logger.error(f"Lead generation process failed: {processed_leads['error']} - Details: {processed_leads.get('details','')}")
    elif processed_leads: 
        successful_analyses_count = sum(
            1 for company_data in processed_leads
            if isinstance(company_data, dict) and company_data.get("pain_points") not in [
                "Initial analysis did not run", 
                "Analysis failed - non-string result",
                "Analysis failed - Task creation error", 
                "Analysis failed to return data",
                "Critical: Analysis function returned no data"
            ] and not str(company_data.get("pain_points", "")).startswith("Analysis skipped")
               and not str(company_data.get("pain_points", "")).startswith("Analysis failed (")
        )
        logger.info(f"\n--- Local Execution Summary (agent_runner.py) ---")
        logger.info(f"Client: {SJ_MORSE_PROFILE['CLIENT_NAME']}")
        logger.info(f"Total Entries Processed (attempts): {len(processed_leads)}")
        logger.info(f"Successfully Analyzed Entries: {successful_analyses_count}")
        
        # Log counts for segments that were actually processed
        processed_segment_names_in_run = set(s_conf.get("SEGMENT_NAME") for s_conf in segments_to_actually_process) if 'segments_to_actually_process' in locals() and segments_to_actually_process else \
                                         set(s_conf.get("SEGMENT_NAME") for s_conf in SJ_MORSE_PROFILE.get("TARGET_SEGMENTS",[]))


        for s_name in processed_segment_names_in_run:
            count = sum(1 for c_data in processed_leads if isinstance(c_data, dict) and c_data.get("segment_name_internal") == s_name)
            logger.info(f"  Entries for Processed Segment '{s_name}': {count}")
        logger.info(f"-------------------------------------------------\n")

        output_file_path = Config.OUTPUT_PATH
        logger.info(f"Writing {len(processed_leads)} processed entries to {output_file_path} for local run...")
        write_to_csv(processed_leads, output_file_path)
    else:
        logger.warning("No company data was processed or returned in this local run of agent_runner.py.")

    logger.info("\n--- End of direct execution for agent_runner.py ---")
