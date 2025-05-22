# url_processor.py

# url_processor.py
import logging
import ast
import re
from urllib.parse import urlparse # Make sure this import is present
from crewai import Crew, Process, CrewOutput, Agent
from config import Config
from utils.parser import parse_url_list

logger = logging.getLogger(__name__)

def perform_search(agents: dict, tasks: list) -> list: # Added type hints for clarity
    """
    Execute search tasks to find relevant URLs using the Research Agent.

    Args:
        agents: Dictionary of initialized agents (expecting 'research' key).
        tasks: List of search-related tasks [plan_task, execute_task].

    Returns:
        List of URLs found during search, potentially filtered.
    """
    url_list = []
    research_agent = agents.get('research') # Get the research agent

    # Check for valid research_agent
    if not research_agent or not isinstance(research_agent, Agent):
        logger.error("Research agent not found or invalid in 'agents' dict within perform_search.")
        return []
    # Basic check on tasks list
    if not isinstance(tasks, list) or len(tasks) < 1: # Typically 2 tasks: plan & execute
        logger.error("Invalid or empty tasks list provided to perform_search.")
        return []

    try:
        logger.info(f"--- Kicking off Search Tasks for agent: {research_agent.role} ---")

        search_crew = Crew(
            agents=[research_agent], # Use the specific Research Agent
            tasks=tasks,
            process=Process.sequential,
            verbose=False # Set to True for detailed CrewAI step logs during debugging
        )

        search_results_object = search_crew.kickoff()
        logger.info(f"--- Search Tasks Finished for agent: {research_agent.role} ---")

        raw_output = None
        if search_results_object:
            if isinstance(search_results_object, CrewOutput):
                raw_output = search_results_object.raw
                logger.debug("Extracted raw output from CrewOutput object.")
            elif isinstance(search_results_object, str):
                raw_output = search_results_object
                logger.debug("Received string output directly.")
            else:
                logger.warning(f"Search Crew returned unexpected type: {type(search_results_object)}")

            if raw_output is not None:
                logger.debug(f"RAW OUTPUT from Research Agent BEFORE parsing URL list:\n---\n{raw_output[:500]}...\n---") # Log snippet
                url_list = parse_url_list(raw_output)
                
                if url_list:
                    logger.info(f"Successfully parsed {len(url_list)} URLs from research agent output.")
                    
                    # --- START OF TLD FILTERING LOGIC ---
                    disallowed_country_tlds = [
                        '.ac', '.ad', '.ae', '.af', '.ag', '.ai', '.al', '.am', '.an', '.ao', '.aq', '.ar', '.as', '.at', '.au', 
                        '.aw', '.ax', '.az', '.ba', '.bb', '.bd', '.be', '.bf', '.bg', '.bh', '.bi', '.bj', '.bm', '.bn', '.bo', 
                        '.br', '.bs', '.bt', '.bv', '.bw', '.by', '.bz', '.ca', '.cc', '.cd', '.cf', '.cg', '.ch', '.ci', '.ck', 
                        '.cl', '.cm', '.cn', '.co', '.cr', '.cu', '.cv', '.cx', '.cy', '.cz', '.de', '.dj', '.dk', '.dm', '.do', 
                        '.dz', '.ec', '.ee', '.eg', '.er', '.es', '.et', '.eu', '.fi', '.fj', '.fk', '.fm', '.fo', '.fr', '.ga', 
                        '.gb', '.gd', '.ge', '.gf', '.gg', '.gh', '.gi', '.gl', '.gm', '.gn', '.gp', '.gq', '.gr', '.gs', '.gt', 
                        '.gu', '.gw', '.gy', '.hk', '.hm', '.hn', '.hr', '.ht', '.hu', '.id', '.ie', '.il', '.im', '.in', '.io', 
                        '.iq', '.ir', '.is', '.it', '.je', '.jm', '.jo', '.jp', '.ke', '.kg', '.kh', '.ki', '.km', '.kn', '.kp', 
                        '.kr', '.kw', '.ky', '.kz', '.la', '.lb', '.lc', '.li', '.lk', '.lr', '.ls', '.lt', '.lu', '.lv', '.ly', 
                        '.ma', '.mc', '.md', '.me', '.mg', '.mh', '.mk', '.ml', '.mm', '.mn', '.mo', '.mp', '.mq', '.mr', '.ms', 
                        '.mt', '.mu', '.mv', '.mw', '.mx', '.my', '.mz', '.na', '.nc', '.ne', '.nf', '.ng', '.ni', '.nl', '.no', 
                        '.np', '.nr', '.nu', '.nz', '.om', '.pa', '.pe', '.pf', '.pg', '.ph', '.pk', '.pl', '.pm', '.pn', '.pr', 
                        '.ps', '.pt', '.pw', '.py', '.qa', '.re', '.ro', '.rs', '.ru', '.rw', '.sa', '.sb', '.sc', '.sd', '.se', 
                        '.sg', '.sh', '.si', '.sj', '.sk', '.sl', '.sm', '.sn', '.so', '.sr', '.st', '.sv', '.sy', '.sz', '.tc', 
                        '.td', '.tf', '.tg', '.th', '.tj', '.tk', '.tl', '.tm', '.tn', '.to', '.tp', '.tr', '.tt', '.tv', '.tw', 
                        '.tz', '.ua', '.ug', '.uk', '.uy', '.uz', '.va', '.vc', '.ve', '.vg', '.vi', '.vn', '.vu', '.wf', '.ws', 
                        '.ye', '.yt', '.za', '.zm', '.zw'
                    ] # This is a list of ccTLDs we generally want to filter out if not ".us"

                    filtered_urls = []
                    for url_str in url_list:
                        try:
                            parsed = urlparse(url_str)
                            hostname = parsed.hostname
                            if hostname:
                                domain_parts = hostname.lower().split('.')
                                is_disallowed = False
                                if len(domain_parts) >= 2:
                                    # Check the most specific part of the TLD (e.g., 'uk' in 'co.uk', 'com' in 'example.com')
                                    # If this part (e.g. ".uk") is in our disallowed_country_tlds list, then filter it.
                                    # We allow ".us" implicitly by not having it in disallowed_country_tlds.
                                    # We also handle cases like "company.co" - ".co" is a ccTLD (Colombia) but often used generically.
                                    # This simple logic might misclassify some .co domains if they are truly Colombian and not desired.
                                    # A more robust solution for TLDs is `tldextract` library.
                                    
                                    # Check if any part of the TLD structure matches a disallowed ccTLD
                                    # For example, if domain is "site.co.uk", it checks ".uk", then ".co.uk"
                                    # If domain is "site.com.br", it checks ".br", then ".com.br"
                                    
                                    # Check simple TLD like .de, .fr
                                    if f".{domain_parts[-1]}" in disallowed_country_tlds:
                                        is_disallowed = True
                                    # Check common compound TLDs like .co.uk, .com.au
                                    elif len(domain_parts) >= 3 and f".{domain_parts[-2]}.{domain_parts[-1]}" in disallowed_country_tlds:
                                        is_disallowed = True
                                    
                                if not is_disallowed:
                                    filtered_urls.append(url_str)
                                else:
                                    logger.debug(f"Filtering out URL due to disallowed TLD: {url_str} (hostname: {hostname})")
                            else:
                                # If no hostname (e.g., relative URL, though parser should handle this), keep it for now.
                                # parse_url_list should ideally return absolute URLs.
                                filtered_urls.append(url_str) 
                        except Exception as e:
                            logger.warning(f"Could not parse URL for TLD filtering: {url_str} - {e}. Keeping URL.")
                            filtered_urls.append(url_str)

                    if len(filtered_urls) < len(url_list):
                        logger.info(f"Filtered out {len(url_list) - len(filtered_urls)} URLs based on disallowed TLDs. Remaining: {len(filtered_urls)}")
                    url_list = filtered_urls
                    # --- END OF TLD FILTERING LOGIC ---
                else:
                    logger.info("URL parser returned no URLs from research agent output.")
            else:
                logger.error("NO RAW OUTPUT string could be extracted from search_results_object.")
                logger.warning("Cannot parse or filter URLs because raw output string could not be extracted.")
        else:
            logger.warning(f"Search Crew for agent {research_agent.role} did not return any output object.")

    except Exception as e:
        logger.error(f"Search Crew execution or URL processing error for agent {research_agent.role}: {e}", exc_info=True)

    return url_list
