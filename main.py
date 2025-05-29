# main.py (for Google Cloud Function deployment)
import functions_framework
import json
import os
import logging
import sys # <<<<<<<<<<<< ADD THIS
import pathlib # <<<<<<<<<<<< ADD THIS

# --- Add current directory to sys.path ---
# This helps Python find sibling modules like agent_runner.py when main.py is run by functions-framework
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
# --- End sys.path modification ---

# Now try your project imports
try:
    from agent_runner import run_lead_generation_process
    # If 'tools' was globally defined in agent_runner.py and you need it here, import it.
    # However, run_lead_generation_process should ideally use the tools dict defined within agent_runner's scope.
    # from agent_runner import tools # Only if 'tools' from agent_runner is truly needed globally by THIS main.py

    from config import Config, SJ_MORSE_PROFILE 
    # agents.py is imported by agent_runner.py, not usually needed directly in this main.py
    # from agents import initialize_agents 
    # Tools are used by agents, which are initialized within agent_runner.py.
    # Direct tool imports here are only if this main.py was to use them, which it doesn't.
    # from tools.scraper_tools import generic_scraper_tool 
    # from tools.unified_email_finder import unified_email_finder_tool
    # from tools.llm_tools import analyze_pain_points_tool
    # from tools.search_tools import web_search_tool
except ImportError as e:
    # Fallback basic logging if the main logger setup (e.g. from agent_runner or Config) hasn't run
    logging.basicConfig(level="DEBUG") 
    initial_logger = logging.getLogger(__name__)
    initial_logger.critical(f"CRITICAL IMPORT ERROR in main.py (GCP Handler): {e}. Current sys.path: {sys.path}", exc_info=True)
    raise # Re-raise the error so functions-framework fails clearly

# Configure logging for this specific main.py if needed,
# or rely on agent_runner.py's global logging setup.
# For simplicity, let's assume agent_runner's Config.configure_logging() is sufficient if agent_runner gets imported.
logger = logging.getLogger(__name__) # Get a logger for this file after successful imports

@functions_framework.http
def sj_morse_lead_generator(request): # 'request' is a Flask request object
    """HTTP Cloud Function to trigger SJ Morse lead generation."""
    
    # --- Basic Authentication (Phase 3 - Simple Shared Secret) ---
    expected_api_key = os.getenv("MY_SHARED_API_KEY") 
    received_api_key = request.headers.get("X-API-Key")

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
            
            # Call your core logic from agent_runner.py
            results = run_lead_generation_process() 

            if isinstance(results, dict) and "error" in results:
                logger.error(f"Lead generation process returned an error: {results}")
                return (json.dumps(results), 500, {"Content-Type": "application/json"})

            processed_count = len(results) if isinstance(results, list) else 'unknown amount of'
            logger.info(f"Lead generation process completed. Returning {processed_count} companies.")
            return (json.dumps(results), 200, {"Content-Type": "application/json"})

        except Exception as e:
            logger.error(f"Unhandled exception in sj_morse_lead_generator: {e}", exc_info=True)
            return (json.dumps({"error": "Internal server error", "details": str(e)}), 500, {"Content-Type": "application/json"})
    else:
        logger.warning(f"Unsupported HTTP method: {request.method} for sj_morse_lead_generator. Use POST.")
        return (json.dumps({"error": "Method not allowed. Use POST."}), 405, {"Content-Type": "application/json"})
