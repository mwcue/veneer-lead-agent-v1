# company_extractor.py
import logging
import ast
import re
import time
from bs4 import BeautifulSoup
from crewai import Crew, Process, CrewOutput, Agent, Task
from config import Config # For GENERIC_COMPANY_NAMES
# Import task creators from tasks.py
from tasks import create_analysis_task, create_review_task
# Use the more robust parser from utils.parser for consistency
from utils.parser import parse_company_data as parse_company_website_list
from tools.scraper_tools import generic_scraper_tool   # <-- NEW


logger = logging.getLogger(__name__)

# parse_company_website_list is now aliased from utils.parser.parse_company_data

def parse_analysis_results(result: str) -> dict:
    """
    Parse the analysis results to extract email and pain points.
    This function is adapted to better handle varied LLM outputs.
    """
    logger.debug("Parsing analysis results...")

    if not isinstance(result, str):
        logger.warning(f"Analysis result is not a string: {type(result)}. Cannot parse.")
        return {"email": "", "pain_points": "Analysis failed - non-string result"}

    # Standardize by removing potential "FINAL ANSWER:" prefix
    cleaned_result = result.strip()
    if cleaned_result.upper().startswith("FINAL ANSWER:"):
        cleaned_result = cleaned_result.split(":", 1)[1].strip()

    email = ""
    pain_points_str = ""

    # --- Email Extraction ---
    # Regex for finding email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    email_matches = re.findall(email_pattern, cleaned_result)
    
    # Filter out common non-contact/false-positive emails
    invalid_email_domains_or_parts = [
        'example.com', 'yourdomain.com', 'test.com', 'sentry.io',
        'wixpress.com', 'wordpress.org', 'schemas.microsoft.com',
        'localhost', 'example.org', 'yourname@', 'email@', 'contact@', 'info@', 'sales@', # if too generic without specific company domain
        '.png', '.jpg', '.gif', '.webp', '.svg', # Emails ending in image extensions
        'u003e', 'u003c' # unicode escapes sometimes found in malformed emails
    ]
    valid_emails = []
    for e in email_matches:
        e_lower = e.lower()
        if not any(invalid in e_lower for invalid in invalid_email_domains_or_parts):
            # Further check: avoid emails that are just placeholders like "contact@" + generic domain
            if e_lower.startswith(('contact@', 'info@', 'sales@')) and e_lower.split('@')[1] in ['domain.com', 'company.com']:
                continue
            valid_emails.append(e)

    if valid_emails:
        email = valid_emails[0]  # Take the first plausible one
        logger.debug(f"Extracted email: {email}")
    else:
        logger.debug("No valid email found in analysis results.")

    # --- Pain Points Extraction ---
    # Try to find sections explicitly labeled, more robustly
    # Order of patterns matters: more specific first
    pain_point_patterns = [
        r"(?:Pain Points|Key Challenges|Identified Opportunities|Analysis Summary|Business Needs|Client Issues)\s*:\s*\n?(.*?)(?:Email:|Contact Email:|Contact:|Suggested Decision Makers:|Conclusion:|\Z)",
        r"Pain Points\s*for\s*Sponsorship\s*:\s*\n?(.*?)(?:Email:|Contact Email:|\Z)", # Specific to old HR context, less likely now
        r"\d\.\s*(.*?)(?:\n\d\.\s|\n\n|\Z)" # Try to capture numbered lists if no explicit label
    ]
    
    extracted_block = None
    for pattern in pain_point_patterns:
        match = re.search(pattern, cleaned_result, re.IGNORECASE | re.DOTALL)
        if match:
            extracted_block = match.group(1).strip()
            if len(extracted_block) > 20: # Ensure it's a substantial block
                logger.debug(f"Found pain points block using pattern: {pattern}")
                break # Use the first successful match
    
    if extracted_block:
        pain_points_str = extracted_block
    else:
        # Fallback: if an email was found, take the text that is NOT the email.
        # Prioritize text after the email if substantial, otherwise before, or the whole thing.
        if email:
            parts = cleaned_result.split(email, 1)
            content_after_email = parts[1].strip() if len(parts) > 1 else ""
            content_before_email = parts[0].strip()

            if len(content_after_email) > 20:
                pain_points_str = content_after_email
            elif len(content_before_email) > 20:
                pain_points_str = content_before_email
            else: # If both are short, and email was found, it implies the rest might be pain points.
                pain_points_str = cleaned_result.replace(email, "").strip()
        else:
            # If no email and no specific block, the whole result is potentially pain points.
            pain_points_str = cleaned_result
        logger.debug("No specific pain points block found, using fallback extraction.")

    # Clean up common list markers and leading/trailing whitespace from the extracted pain points
    pain_points_str = re.sub(r"^\s*[-\*•\d\.\s]+", "", pain_points_str, flags=re.MULTILINE).strip()
    pain_points_str = re.sub(r"\n\s*[-\*•\d\.\s]+", "\n", pain_points_str).strip() # Clean multi-line lists

    if not pain_points_str.strip() or pain_points_str == email:
        pain_points_str = "No specific pain points identified in the output."
        logger.debug("Pain points string was empty or just the email after cleaning.")

    logger.debug(f"Final parsed pain points (first 100 chars): {pain_points_str[:100]}...")
    return {"email": email, "pain_points": pain_points_str}


def extract_companies_from_url(url: str, agents: dict, extraction_task: Task) -> list:
    """
    Extract company information from a given URL using the research agent.
    (This function's core logic remains, ensure `extraction_task` is correctly created)
    """
    extracted_company_data = []
    research_agent = agents.get('research')

    if not research_agent or not isinstance(research_agent, Agent):
        logger.error(f"Research agent not found or invalid for URL extraction: {url}")
        return []
    if not extraction_task or not isinstance(extraction_task, Task):
        logger.error(f"Invalid extraction_task provided for URL: {url}")
        return []

    if not extracted_company_data:
        try:
            page_html = generic_scraper_tool(url)
            extracted_company_data = _fallback_list_parser(page_html)
            if extracted_company_data:
                logger.info(
                    f"[Fallback] extracted {len(extracted_company_data)} companies from {url}"
                )
        except Exception as e:
            logger.warning(f"[Fallback] fetch failed for {url}: {e}")


    try:
        extraction_crew = Crew(
            agents=[research_agent], # Only the research agent performs this task
            tasks=[extraction_task],
            process=Process.sequential,
            verbose=False # Set to True for debugging CrewAI steps
        )
        logger.debug(f"  Kicking off extraction crew for URL: {url}...")
        extraction_result_object = extraction_crew.kickoff()
        logger.debug(f"  Extraction crew finished for {url}.")

        raw_output = None
        if isinstance(extraction_result_object, CrewOutput):
            raw_output = extraction_result_object.raw
        elif isinstance(extraction_result_object, str):
            raw_output = extraction_result_object
        
        if raw_output:
            # ---- Primary LLM-style parser -------------------------------
            extracted_company_data = parse_company_website_list(raw_output)

            # ---- Fallback #1: HTML scrape if nothing found --------------
            if not extracted_company_data:
                try:
                    page_html = generic_scraper_tool(url)          # fetch HTML with polite UA
                    extracted_company_data = _fallback_list_parser(page_html)
                    if extracted_company_data:
                        logger.info(f"  Fallback parser extracted {len(extracted_company_data)} companies from {url}.")
                except Exception as fetch_err:
                    logger.warning(f"  Fallback HTML fetch failed for {url}: {fetch_err}")

            # ---- Logging ------------------------------------------------
            if extracted_company_data:
                logger.info(f"  Extracted {len(extracted_company_data)} company/website pairs from {url}.")
            else:
                logger.info(f"  No companies extracted from {url}.")
        else:
            logger.warning(f"  Extraction crew returned no parsable output for {url}.")

    except Exception as e:
        logger.error(f"  Error during company extraction process for '{url}': {e}", exc_info=True)

    return extracted_company_data


def analyze_company(company_name: str, company_website: str, agents: dict, segment_config: dict, client_profile: dict):
    """
    Analyze a company to find email and pain points, including a review cycle,
    using agents specific to the company's segment.

    Args:
        company_name: Name of the company.
        company_website: Website URL of the company.
        agents: Dictionary of ALL initialized agents.
        segment_config: Configuration dictionary for the specific target segment.
        client_profile: Overall client profile dictionary.

    Returns:
        Dictionary with company analysis data.
    """
    segment_name = segment_config.get("SEGMENT_NAME", "Unknown Segment")
    client_name = client_profile.get("CLIENT_NAME", "Our Client")

    # Initialize results with basic info and segment
    final_company_data = {
        "name": company_name,
        "website": company_website,
        "pain_points": "Initial analysis did not run",
        "contact_email": "",
        "segment_name_internal": segment_name, # For internal tracking
        "category": segment_name # For CSV compatibility with old format
    }

def _fallback_list_parser(html: str) -> list[dict]:
    """
    Very lightweight parser that tries to pull a company-name list
    from common directory pages (Wikipedia tables, plain UL/OL, etc.).
    Returns list of {"name": .., "website": ""}.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    # ── 1  Wikipedia «wikitable» (rank, company, …) ────────────
    for tr in soup.select("table.wikitable tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            name = tds[1].get_text(" ", strip=True)
            if name and len(name.split()) > 1:
                rows.append({"name": name, "website": ""})

    # ── 2  Plain <li> text lists  ──────────────────────────────
    if not rows:
        for li in soup.select("ul li, ol li"):
            txt = li.get_text(" ", strip=True)
            # Simple regex: skip very short / all-caps / numeric lines
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9 &.,'()-]{4,}", txt):
                rows.append({"name": txt, "website": ""})

    return rows

    # --- Determine Agent Keys based on Segment Name ---
    analyzer_agent_key = f"{segment_name}_analyzer"
    reviewer_agent_key = f"{segment_name}_reviewer"

    analysis_agent = agents.get(analyzer_agent_key)
    reviewer_agent = agents.get(reviewer_agent_key)

    if not analysis_agent or not isinstance(analysis_agent, Agent):
        logger.error(f"  '{analyzer_agent_key}' not found or invalid for company '{company_name}'. Skipping analysis.")
        final_company_data["pain_points"] = f"Analysis skipped - {analyzer_agent_key} agent missing"
        return final_company_data

    # Reviewer agent is optional for the analysis part to proceed
    if not reviewer_agent or not isinstance(reviewer_agent, Agent):
        logger.warning(f"  '{reviewer_agent_key}' not found or invalid for '{company_name}'. Review cycle will be skipped.")

    try:
        # === Stage 1: Initial Analysis ===
        logger.info(f"      >>> Starting analysis for '{company_name}' (Segment: {segment_name}) using {analyzer_agent_key}...")

        # Create analysis_task using the selected agent and full context
        analysis_task = create_analysis_task(
            company_name,
            company_website,
            analysis_agent, # Pass the specific analyzer agent
            segment_config,
            client_profile
        )

        if analysis_task is None:
            logger.error(f"      Failed to create analysis task for '{company_name}'. Skipping analysis.")
            final_company_data["pain_points"] = "Analysis failed - Task creation error"
            return final_company_data

        # Create and run the analysis crew
        analysis_crew = Crew(
            agents=[analysis_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=False # Set to True for debugging CrewAI steps
        )
        analysis_result_object = analysis_crew.kickoff()
        logger.debug(f"      <<< Initial analysis finished for '{company_name}'.")

        # Parse initial results
        initial_email = ""
        initial_pain_points = "Initial analysis failed: No output object."

        raw_output = None
        if isinstance(analysis_result_object, CrewOutput):
            raw_output = analysis_result_object.raw
        elif isinstance(analysis_result_object, str):
            raw_output = analysis_result_object
        
        if raw_output:
            parsed_initial = parse_analysis_results(raw_output)
            initial_email = parsed_initial.get('email', '')
            initial_pain_points = parsed_initial.get('pain_points', 'Initial analysis parsing failed')
            logger.debug(f"      Parsed initial analysis - Email: '{initial_email}', Points: '{initial_pain_points[:100]}...'")
        else:
            logger.warning(f"      Initial analysis for {company_name} returned output, but raw string could not be extracted.")
            initial_pain_points = "Initial analysis failed: Could not extract raw output."

        final_company_data["contact_email"] = initial_email
        final_company_data["pain_points"] = initial_pain_points

        # === Stage 2: Review Cycle ===
        if not reviewer_agent: # Check if reviewer agent is valid before proceeding
            logger.warning(f"      Skipping review cycle for '{company_name}' because reviewer agent ('{reviewer_agent_key}') is missing.")
        elif not initial_pain_points or initial_pain_points.startswith("Initial analysis failed") or initial_pain_points.startswith("Analysis failed") or initial_pain_points.startswith("Analysis skipped"):
            logger.warning(f"      Skipping review cycle for '{company_name}' due to initial analysis failure or lack of valid points.")
        else:
            logger.info(f"      >>> Starting pain point review for '{company_name}' (Segment: {segment_name}) using {reviewer_agent_key}...")
            review_task = create_review_task(
                company_name,
                company_website,
                initial_pain_points,
                reviewer_agent, # Pass the specific reviewer agent
                segment_config,
                client_profile
            )

            if review_task is None:
                logger.error(f"      Failed to create review task for '{company_name}'. Skipping review.")
            else:
                try:
                    # Reviewer agent executes its task directly (not in a new Crew for a single task)
                    # Some CrewAI versions might wrap single task execution in a simple crew run.
                    # For simplicity with a single agent and task, directly using agent.execute_task if available,
                    # or wrapping in a minimal crew. The example used execute_task previously.
                    # Let's stick to Crew for consistency in how tasks are run with agents.
                    review_crew = Crew(
                        agents=[reviewer_agent],
                        tasks=[review_task],
                        process=Process.sequential,
                        verbose=False
                    )
                    review_result_object = review_crew.kickoff()
                    logger.debug(f"      <<< Review cycle finished for '{company_name}'.")

                    review_raw_output = None
                    if isinstance(review_result_object, CrewOutput):
                        review_raw_output = review_result_object.raw
                    elif isinstance(review_result_object, str):
                        review_raw_output = review_result_object

                    if review_raw_output:
                        parsed_review = parse_analysis_results(review_raw_output) # Assuming review output is similar format
                        reviewed_pain_points = parsed_review.get('pain_points')

                        if reviewed_pain_points and not reviewed_pain_points.startswith("Analysis failed") and reviewed_pain_points != initial_pain_points:
                            if len(reviewed_pain_points) > 10 and reviewed_pain_points != "No specific pain points identified in the output.": # Ensure meaningful review
                                logger.info(f"      Review cycle provided refined pain points for '{company_name}'.")
                                final_company_data["pain_points"] = reviewed_pain_points
                            else:
                                logger.info(f"      Review provided minimal/no content, keeping initial points for '{company_name}'.")
                        elif reviewed_pain_points == initial_pain_points:
                            logger.info(f"      Review validated initial pain points for '{company_name}'.")
                        else:
                            logger.warning(f"      Review output parsing failed or yielded no new points for {company_name}. Using initial points.")
                    else:
                        logger.warning(f"      Review task for {company_name} returned no parsable output. Using initial points.")

                except Exception as review_err:
                    logger.error(f"      Error during review task execution for '{company_name}': {review_err}", exc_info=True)
                    logger.warning(f"      Using initial pain points for {company_name} due to review execution error.")
        
        return final_company_data

    except Exception as e:
        logger.error(f"      Overall error during company analysis process for '{company_name}' (Segment: {segment_name}): {e}", exc_info=True)
        final_company_data["pain_points"] = f"Analysis failed (Segment: {segment_name}): Exception - {type(e).__name__}"
        if not final_company_data.get("contact_email"):
            final_company_data["contact_email"] = "" # Ensure email key exists
        return final_company_data
