# agent_runner.py
# formerly main.py when deployed on laptop
"""
SJ Morse Lead Generation Agent (Adapted from HR & Regional B2B)

This script automates the process of identifying companies for SJ Morse,
a manufacturer of custom architectural wood veneer panels.

It focuses on predefined target segments, analyzes their potential needs
for veneer products, and gathers publicly available information.

The system uses the CrewAI framework to organize multiple AI agents.
The specific agents and their roles will be adapted to target segments like:
- General Contractors & Design-Build Firms
- Architects & Interior Designers

The resulting prospect data is saved to a CSV file (currently maintaining original format).

Usage:
    python main.py

Environment Variables:
    OPENAI_API_KEY: OpenAI API key for LLM access (or other provider keys)
    SERPER_API_KEY: Serper API key for web search functionality
    LLM_PROVIDER: Specifies which LLM provider to use (e.g., "openai", "anthropic")

    Optional variables can be found in the config.py file
"""

import time
import logging
from dotenv import load_dotenv

# Import our custom modules
from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
# Import Config and the new SJ_MORSE_PROFILE
from config import Config, SJ_MORSE_PROFILE
# Import task creators
from tasks import create_search_tasks, create_extraction_task
from utils.logging_utils import get_logger, ErrorCollection

# Configure logging
Config.configure_logging()
logger = get_logger(__name__) # Ensure logger is fetched after configuration

# Load environment variables
load_dotenv()

# Import tools and initialize agents
error_collector = ErrorCollection()
try:
    # --- Tool Imports ---
    from tools.scraper_tools import generic_scraper_tool
    from tools.unified_email_finder import unified_email_finder_tool
    from tools.llm_tools import analyze_pain_points_tool # This tool's internal prompt will need significant change
    from tools.search_tools import web_search_tool
    # --- Agent Initialization ---
    # initialize_agents will be adapted to create agents based on SJ_MORSE_PROFILE segments
    from agents import initialize_agents

    if web_search_tool is None:
        error_collector.add("Tool Initialization",
                           ValueError("Web Search Tool failed to initialize"),
                           fatal=True)
    else:
        logger.info("Custom tools imported successfully.")

    missing_keys = Config.validate()
    if missing_keys:
        error_collector.add("Configuration",
                           ValueError(f"Missing required environment variables: {', '.join(missing_keys)}"),
                           fatal=True)

    # Log API key presence for the configured LLM provider and Serper
    logger.info(f"LLM_PROVIDER set to: {Config.LLM_PROVIDER}")
    if Config.LLM_PROVIDER == "openai":
        logger.info(f"OPENAI_API_KEY presence: {'Yes' if Config.OPENAI_API_KEY else 'No'}")
    elif Config.LLM_PROVIDER == "anthropic":
        logger.info(f"ANTHROPIC_API_KEY presence: {'Yes' if Config.ANTHROPIC_API_KEY else 'No'}")
    # Add more elif for other providers if you log their key presence specifically
    logger.info(f"SERPER_API_KEY presence: {'Yes' if Config.SERPER_API_KEY else 'No'}")

except ImportError as e:
    error_collector.add("Module Import", e, fatal=True)
except Exception as e:
    error_collector.add("Initialization", e, fatal=True)

if error_collector.has_fatal_errors():
    logger.error("Fatal errors during initialization. Exiting.")
    logger.error(error_collector.get_summary())
    exit(1)

# Initialize tools dictionary (remains largely the same for now)
tools = {
    'web_search': web_search_tool,
    'generic_scraper': generic_scraper_tool,
    'email_finder': unified_email_finder_tool,
    'pain_point_analyzer': analyze_pain_points_tool
}

# Main execution block
if __name__ == "__main__":
    logger.info(f"\n--- Starting Lead Generation Crew for Client: {SJ_MORSE_PROFILE['CLIENT_NAME']} ---")

    all_processed_companies = []
    # Keep track of websites processed in this specific run to avoid re-analyzing
    processed_websites_this_run = set()

    # Initialize agents
    # This function will be updated in agents.py to create agents tailored for SJ Morse segments
    try:
        agents = initialize_agents(tools, SJ_MORSE_PROFILE) # Pass SJ_MORSE_PROFILE to agent initialization
        logger.info(f"Agents initialized successfully. Available agents: {list(agents.keys())}")
        # TODO: Update agent key check once agents.py is refactored
        # e.g., expected_keys = {'research', 'gc_analyzer', 'gc_reviewer', 'architect_analyzer', 'architect_reviewer'}
        # if not expected_keys.issubset(agents.keys()):
        #     raise ValueError(f"Expected SJ Morse specific agents not found. Got: {list(agents.keys())}")
    except Exception as e:
        error_collector.add("Agent Initialization", e, fatal=True)
        logger.error(f"Fatal error during agent initialization: {e}")
        logger.error(error_collector.get_summary())
        exit(1)

    # --- Loop through each target segment defined in SJ_MORSE_PROFILE ---
    for segment_config in SJ_MORSE_PROFILE["TARGET_SEGMENTS"]:
        segment_name = segment_config["SEGMENT_NAME"]
        logger.info(f"\n>>> Processing Segment: {segment_name} <<<")

        # Step 1 (per segment): Find relevant URLs for this segment
        # create_search_tasks will be adapted in tasks.py to use segment_config
        logger.info(f"  Creating search tasks for segment: {segment_name}...")
        search_tasks = create_search_tasks(agents['research'], segment_config) # Pass research agent and segment_config
        
        if not search_tasks:
            logger.error(f"  Failed to create search tasks for segment: {segment_name}. Skipping segment.")
            continue
            
        logger.info(f"  Performing search for segment: {segment_name}...")
        url_list = perform_search(agents, search_tasks) # perform_search uses agents['research']

        if not url_list:
            logger.warning(f"  No URLs found by Research Agent for segment: {segment_name}. Skipping to next segment.")
            continue

        logger.info(f"  Found {len(url_list)} URLs for {segment_name}. Processing up to {Config.MAX_URLS_TO_PROCESS} URLs.")
        urls_to_process = url_list[:Config.MAX_URLS_TO_PROCESS]

        for i, target_url in enumerate(urls_to_process):
            logger.info(f"\n    Processing URL {i+1}/{len(urls_to_process)} for {segment_name}: {target_url}")

            # Step 2a (per URL): Extract Companies
            # create_extraction_task uses the generic research agent.
            logger.debug(f"      Creating extraction task for URL: {target_url}...")
            extraction_task = create_extraction_task(target_url, agents['research']) # Pass research agent
            
            if not extraction_task:
                logger.error(f"      Failed to create extraction task for {target_url}. Skipping URL.")
                continue

            logger.debug(f"      Extracting companies from URL: {target_url}...")
            # extract_companies_from_url uses the research agent and its extraction_task
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

                # Intra-Run Duplicate Check (website normalization)
                normalized_website = company_website.strip().lower()
                if normalized_website.startswith('www.'):
                   normalized_website = normalized_website[4:]
                if normalized_website.endswith('/'):
                    normalized_website = normalized_website[:-1]

                if normalized_website in processed_websites_this_run:
                    logger.info(f"        Skipping already processed website in this run: '{company_name}' ({company_website})")
                    continue
                
                # Skip generic names
                if company_name.lower() in Config.GENERIC_COMPANY_NAMES:
                    logger.info(f"        Skipping generic company name: '{company_name}'")
                    continue

                processed_websites_this_run.add(normalized_website) # Add before analysis

                logger.info(f"        Analyzing '{company_name}' ({company_website}) for segment: {segment_name}")

                # Step 2b (per company): Analyze Company
                # analyze_company will be adapted in company_extractor.py
                # It will need the segment_config to select the correct analyzer/reviewer agents
                # and to pass segment-specific context to task creation.
                company_analysis_data = analyze_company(
                    company_name=company_name,
                    company_website=company_website,
                    agents=agents, # Pass all agents
                    segment_config=segment_config, # Pass the specific segment_config
                    client_profile=SJ_MORSE_PROFILE # Pass the overall client profile for USPs etc.
                )

                if company_analysis_data:
                    # Store all gathered data.
                    # The 'category' field from the original structure will be replaced by segment_name
                    company_analysis_data["source_url"] = target_url
                    company_analysis_data["segment_name_internal"] = segment_name # For internal use
                    
                    # To maintain compatibility with the old CSV format,
                    # we will add a 'category' key that mirrors segment_name for now.
                    # This is a temporary measure.
                    company_analysis_data["category"] = segment_name

                    all_processed_companies.append(company_analysis_data)
                    logger.info(f"        Successfully analyzed '{company_name}'. Email: {company_analysis_data.get('contact_email', 'N/A')}, Points: {company_analysis_data.get('pain_points', 'N/A')[:50]}...")
                else:
                    # Log if analysis returns None, though analyze_company should return a dict with error info
                    logger.error(f"        Analysis for '{company_name}' (segment: {segment_name}) returned no data. This might indicate an issue in analyze_company.")
                    # Add a placeholder if necessary to track failures
                    all_processed_companies.append({
                        "name": company_name,
                        "website": company_website,
                        "pain_points": "Analysis failed to return data",
                        "contact_email": "",
                        "source_url": target_url,
                        "category": segment_name, # For CSV compatibility
                        "segment_name_internal": segment_name
                    })


                # Optional short delay between analyzing companies from the same URL
                time.sleep(Config.API_RETRY_DELAY / 2 if Config.API_RETRY_DELAY > 0 else 0.5)

        logger.info(f"  --- Finished processing URLs for segment: {segment_name} ---")
    logger.info("--- Finished Processing All Segments ---")

    # Step 3: Write Final CSV Output
    if all_processed_companies:
        # Log a summary before writing
        successful_analyses_count = sum(
            1 for c in all_processed_companies
            if isinstance(c, dict) and c.get("pain_points") not in [
                "Initial analysis did not run",
                "Analysis failed - non-string result",
                "Analysis failed - Task creation error",
                "Analysis failed to return data" # Our new placeholder
            ] and not str(c.get("pain_points", "")).startswith("Analysis skipped")
               and not str(c.get("pain_points", "")).startswith("Analysis failed (")
        )
        logger.info(f"\n--- Pre-CSV Summary ---")
        logger.info(f"Client: {SJ_MORSE_PROFILE['CLIENT_NAME']}")
        logger.info(f"Total Entries Processed (attempts): {len(all_processed_companies)}")
        logger.info(f"Successfully Analyzed Entries: {successful_analyses_count}")
        for seg_conf in SJ_MORSE_PROFILE["TARGET_SEGMENTS"]:
            s_name = seg_conf["SEGMENT_NAME"]
            count = sum(1 for c in all_processed_companies if isinstance(c,dict) and c.get("segment_name_internal") == s_name)
            logger.info(f"  Entries for Segment '{s_name}': {count}")
        logger.info(f"--------------------------\n")

        logger.info(f"Writing {len(all_processed_companies)} processed entries (includes failures) to {Config.OUTPUT_PATH}...")
        # write_to_csv in output_manager.py will still use the old headers for now.
        # It will look for 'category' (which we've temporarily added) 'name', 'website', 'pain_points', 'contact_email', 'source_url'.
        write_to_csv(all_processed_companies, Config.OUTPUT_PATH)
    else:
        logger.warning("\nNo company data processed in this run. Skipping CSV output.")

    if error_collector.has_errors():
        logger.warning("\n--- Error Summary ---")
        logger.warning(error_collector.get_summary())
        logger.warning("--- End Error Summary ---")

    logger.info("\n--- End of Execution ---")
