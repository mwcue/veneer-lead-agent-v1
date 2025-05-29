# agent_runner.py
import time
import logging
import json # For local testing output if desired
from dotenv import load_dotenv

# Project-specific imports
from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
from config import Config, SJ_MORSE_PROFILE # Ensure SJ_MORSE_PROFILE is correctly defined in config.py
from tasks import create_search_tasks, create_extraction_task # create_analysis_task, create_review_task are used by analyze_company
from utils.logging_utils import get_logger, ErrorCollection
from agents import initialize_agents # Crucial import for agent setup

# --- Global Initializations: These run once when this module is imported ---
Config.configure_logging() # Configure logging settings (e.g., level, format)
logger = get_logger(__name__) # Get a logger specific to this module
load_dotenv() # Load environment variables from .env file

# Initialize tools and perform initial validation globally
# This way, tools and basic config checks are done once.
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

    # Log API key presence for convenience
    logger.info(f"agent_runner.py: LLM_PROVIDER set to: {Config.LLM_PROVIDER}")
    if Config.LLM_PROVIDER == "openai":
        logger.info(f"agent_runner.py: OPENAI_API_KEY presence: {'Yes' if Config.OPENAI_API_KEY else 'No'}")
    logger.info(f"agent_runner.py: SERPER_API_KEY presence: {'Yes' if Config.SERPER_API_KEY else 'No'}")


    if initial_error_collector.has_fatal_errors():
        logger.critical(f"Fatal errors during initial setup of agent_runner.py: {initial_error_collector.get_summary()}")
        # This exception will prevent the module from loading fully if setup fails,
        # which is good because run_lead_generation_process would be unusable.
        raise RuntimeError(f"Fatal initial setup error in agent_runner.py: {initial_error_collector.get_summary()}")
    else:
        logger.info("agent_runner.py: Initial global setup checks passed successfully.")

except ImportError as e_imp:
    logger.critical(f"Fatal ImportError during agent_runner.py global setup: {e_imp}", exc_info=True)
    raise # Re-raise to ensure module loading fails clearly
except Exception as e_gen:
    logger.critical(f"Fatal Exception during agent_runner.py global setup: {e_gen}", exc_info=True)
    raise # Re-raise
# --- End Global Initializations ---


# --- Main Process Function ---
def run_lead_generation_process():
    """
    Runs the full lead generation process for the configured client (SJ Morse) and its target segments.
    Returns a list of processed company data dictionaries.
    """
    run_error_collector = ErrorCollection() # For errors specific to this run

    logger.info(f"\n--- Starting Lead Generation Process within agent_runner for Client: {SJ_MORSE_PROFILE['CLIENT_NAME']} ---")

    all_processed_companies = []
    processed_websites_this_run = set()

    # Initialize agents for this run. Uses the globally defined `tools` dict.
    try:
        # `initialize_agents` is imported from `agents.py`
        # It now expects `tools` (globally defined in this module) and `SJ_MORSE_PROFILE`
        agents = initialize_agents(tools, SJ_MORSE_PROFILE)
        logger.info(f"Agents initialized successfully for run. Available agents: {list(agents.keys())}")
    except Exception as e:
        run_error_collector.add("Agent Initialization for Run", e, fatal=True)
        logger.error(f"Fatal error during agent initialization for this run: {e}", exc_info=True)
        # Return a dictionary indicating error, as the process cannot continue
        return {
            "error": "Agent initialization failed within run_lead_generation_process",
            "details": str(e),
            "processed_companies": all_processed_companies # Likely empty
        }

    if 'research' not in agents or not agents['research']:
        logger.error("Critical: Research agent not found after initialization. Aborting process.")
        return {
            "error": "Research agent missing after initialization.",
            "processed_companies": all_processed_companies
        }

    # Loop through each target segment defined in SJ_MORSE_PROFILE
    for segment_config in SJ_MORSE_PROFILE.get("TARGET_SEGMENTS", []): # Use .get for safety
        segment_name = segment_config.get("SEGMENT_NAME")
        if not segment_name:
            logger.warning("Found a segment in profile without a name. Skipping.")
            continue
        
        logger.info(f"\n>>> Processing Segment: {segment_name} <<<")

        logger.info(f"  Creating search tasks for segment: {segment_name}...")
        search_tasks = create_search_tasks(agents['research'], segment_config)
        
        if not search_tasks:
            logger.error(f"  Failed to create search tasks for segment: {segment_name}. Skipping segment.")
            run_error_collector.add(f"Search Task Creation - {segment_name}", ValueError("Task creation failed"))
            continue
            
        logger.info(f"  Performing search for segment: {segment_name}...")
        # `perform_search` expects the full `agents` dict to find `agents['research']`
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
                    agents=agents, # Pass the whole dictionary of initialized agents
                    segment_config=segment_config,
                    client_profile=SJ_MORSE_PROFILE
                )

                if company_analysis_data: # analyze_company should always return a dict
                    company_analysis_data["source_url"] = target_url # Ensure source_url is added
                    company_analysis_data["segment_name_internal"] = segment_name # Internal tracking
                    company_analysis_data["category"] = segment_name # For CSV compatibility with old format
                    all_processed_companies.append(company_analysis_data)
                    # Log a snippet of pain points for quick check
                    pain_points_snippet = str(company_analysis_data.get('pain_points', 'N/A'))[:70]
                    logger.info(f"        Successfully analyzed '{company_name}'. Email: {company_analysis_data.get('contact_email', 'N/A')}, Pain Points: {pain_points_snippet}...")
                else:
                    # This case should ideally be handled by analyze_company returning a dict with an error message
                    logger.error(f"        Analysis for '{company_name}' (segment: {segment_name}) unexpectedly returned None or falsy value.")
                    # Add a placeholder if truly nothing was returned
                    all_processed_companies.append({
                        "name": company_name, "website": company_website,
                        "pain_points": "Critical: Analysis function returned no data", "contact_email": "",
                        "source_url": target_url, "category": segment_name,
                        "segment_name_internal": segment_name
                    })
                
                # Configurable delay
                sleep_duration = Config.API_RETRY_DELAY / 2 if Config.API_RETRY_DELAY > 0 else 0.5
                if sleep_duration > 0: # Only sleep if duration is positive
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
    # Call the main processing function
    processed_leads = run_lead_generation_process()
    run_end_time = time.time()

    logger.info(f"Total lead generation process completed in {run_end_time - run_start_time:.2f} seconds.")

    if isinstance(processed_leads, dict) and "error" in processed_leads:
        logger.error(f"Lead generation process failed: {processed_leads['error']} - Details: {processed_leads.get('details','')}")
    elif processed_leads: # Check if the list is not empty
        successful_analyses_count = sum(
            1 for company_data in processed_leads
            if isinstance(company_data, dict) and company_data.get("pain_points") not in [
                "Initial analysis did not run", 
                "Analysis failed - non-string result",
                "Analysis failed - Task creation error", 
                "Analysis failed to return data",
                "Critical: Analysis function returned no data"
            ] and not str(company_data.get("pain_points", "")).startswith("Analysis skipped")
               and not str(company_data.get("pain_points", "")).startswith("Analysis failed (") # From company_extractor error case
        )
        logger.info(f"\n--- Local Execution Summary (agent_runner.py) ---")
        logger.info(f"Client: {SJ_MORSE_PROFILE['CLIENT_NAME']}")
        logger.info(f"Total Entries Processed (attempts): {len(processed_leads)}")
        logger.info(f"Successfully Analyzed Entries: {successful_analyses_count}")
        
        for seg_conf in SJ_MORSE_PROFILE.get("TARGET_SEGMENTS", []):
            s_name = seg_conf.get("SEGMENT_NAME", "Unnamed Segment")
            count = sum(1 for c_data in processed_leads if isinstance(c_data, dict) and c_data.get("segment_name_internal") == s_name)
            logger.info(f"  Entries for Segment '{s_name}': {count}")
        logger.info(f"-------------------------------------------------\n")

        # Write to CSV for local runs
        output_file_path = Config.OUTPUT_PATH
        logger.info(f"Writing {len(processed_leads)} processed entries to {output_file_path} for local run...")
        write_to_csv(processed_leads, output_file_path) # from output_manager.py

        # Optional: print a snippet of JSON for API output preview during local testing
        # logger.info("\n--- JSON Output Preview (first 2 entries if available) ---")
        # print(json.dumps(processed_leads[:2], indent=2))
    else:
        logger.warning("No company data was processed or returned in this local run of agent_runner.py.")

    logger.info("\n--- End of direct execution for agent_runner.py ---")
