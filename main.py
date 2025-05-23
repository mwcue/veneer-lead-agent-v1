# main.py (for Google Cloud Function deployment)
import functions_framework
import json
import os
import logging

# Assuming your core logic is now in agent_runner.py
from agent_runner import run_lead_generation_process, tools # Import tools if needed for re-init
from config import Config # To ensure Config is loaded for environment variables

# Configure logging for the Cloud Function environment
# (Cloud Functions often has its own logging integration, but good to be explicit)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

@functions_framework.http
def sj_morse_lead_generator(request): # 'request' is a Flask request object
    """HTTP Cloud Function to trigger SJ Morse lead generation."""
    
    # --- Basic Authentication (Phase 3 - Simple Shared Secret) ---
    # This can be added later, but showing the placement
    expected_api_key = os.getenv("MY_SHARED_API_KEY") # Set in Cloud Function Env Vars
    received_api_key = request.headers.get("X-API-Key")

    if expected_api_key and received_api_key != expected_api_key:
        logger.warning("Unauthorized API key attempt.")
        return (json.dumps({"error": "Unauthorized"}), 401, {"Content-Type": "application/json"})
    elif expected_api_key and not received_api_key:
        logger.warning("Missing API key.")
        return (json.dumps({"error": "API key required"}), 401, {"Content-Type": "application/json"})
    
    logger.info(f"Cloud Function triggered. Request method: {request.method}")
    
    # For Option A (SJ Morse only, no specific input needed from POST body)
    # We just trigger the predefined SJ Morse process
    if request.method == 'POST': # Or GET if you prefer, but POST is common for actions
        try:
            logger.info("Starting SJ Morse lead generation process...")
            # Re-initialize agents if necessary, or ensure global agents are used correctly
            # If agents are initialized globally in agent_runner.py, that might be fine.
            # If they need re-initialization per call due to state or LLM client issues over time:
            # from agents import initialize_agents
            # current_agents = initialize_agents(tools, SJ_MORSE_PROFILE) # Assuming SJ_MORSE_PROFILE is accessible
            
            # Call your core logic
            results = run_lead_generation_process() # This function is imported

            if isinstance(results, dict) and "error" in results:
                logger.error(f"Lead generation process failed: {results}")
                return (json.dumps(results), 500, {"Content-Type": "application/json"})

            logger.info(f"Lead generation process completed. Returning {len(results)} companies.")
            # Return results as JSON
            return (json.dumps(results), 200, {"Content-Type": "application/json"})

        except Exception as e:
            logger.error(f"Error during lead generation: {e}", exc_info=True)
            return (json.dumps({"error": "Internal server error", "details": str(e)}), 500, {"Content-Type": "application/json"})
    else:
        # Handle other methods or return error
        logger.warning(f"Unsupported HTTP method: {request.method}")
        return (json.dumps({"error": "Method not allowed. Use POST."}), 405, {"Content-Type": "application/json"})
