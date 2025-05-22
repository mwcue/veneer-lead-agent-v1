# tools/search_tools.py

import os
import logging
from crewai.tools import BaseTool
from crewai_tools import SerperDevTool
# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Initialize the SerperDevTool ---
# The tool automatically uses the SERPER_API_KEY environment variable
try:
    # Check if the API key is present
    if not os.getenv("SERPER_API_KEY"):
        raise ValueError("SERPER_API_KEY environment variable not found!")

    # Instantiate the tool provided by crewai_tools
    # We can give it a slightly different name/description if we wrap it,
    # but often using it directly is fine if the agent prompts are clear.
    web_search_tool = SerperDevTool()
    logger.info("SerperDevTool initialized successfully.")

    # Optional: Test the tool instance immediately (requires key to be valid)
    # test_results = web_search_tool._run("latest HR tech trends")
    # logger.info(f"Serper Tool Test Results: {test_results[:200]}...") # Print first 200 chars

except ValueError as ve:
    logger.error(f"Configuration error for SerperDevTool: {ve}")
    # Make the tool unusable if the key is missing
    web_search_tool = None # Set to None or handle differently if needed
except Exception as e:
    logger.error(f"Error initializing SerperDevTool: {e}", exc_info=True)
    web_search_tool = None # Set to None on other errors


# --- You could optionally wrap it in your own BaseTool class ---
# This gives you more control over the description or input/output handling if needed.
# Example (Optional):
# class WebSearchToolWrapper(BaseTool):
#     name: str = "Web Search Engine"
#     description: str = (
#         "Performs a web search using the Serper API based on a query. "
#         "Input must be the search query string. Returns search results."
#     )
#     _serper_tool: SerperDevTool = None
#
#     def __init__(self):
#         super().__init__()
#         if web_search_tool: # Use the instance created above if valid
#             self._serper_tool = web_search_tool
#         else:
#             logger.error("SerperDevTool failed to initialize. WebSearchToolWrapper cannot function.")
#
#     def _run(self, search_query: str) -> str:
#         logger.info(f"[Tool: {self.name}] Executing for query: {search_query}")
#         if not self._serper_tool:
#             return "Error: Search tool is not configured due to initialization failure."
#         if not isinstance(search_query, str) or not search_query:
#             return "Error: Invalid search query provided."
#         try:
#             # Use the underlying SerperDevTool's run method
#             return self._serper_tool._run(search_query)
#         except Exception as e:
#             logger.error(f"[Tool: {self.name}] Error during search for '{search_query}': {e}", exc_info=True)
#             return f"Error performing web search for query: {search_query}"
#
# # Instantiate the wrapper tool if using the wrapped approach
# # web_search_tool = WebSearchToolWrapper()

# Export the tool instance directly (simpler approach)
# Ensure it's not None before exporting if you want stricter checks elsewhere
if web_search_tool is None:
     logger.critical("CRITICAL: web_search_tool could not be initialized. Check SERPER_API_KEY and logs.")
     # Depending on desired behavior, you might raise an exception here
     # or allow the program to continue but log the critical failure.
