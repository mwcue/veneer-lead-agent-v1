# agent_runner.py
"""
Central pipeline for SJ Morse lead generation.
Initialises tools, validates config, then exposes
`run_lead_generation_process(selected_segment_names: list | None)`
which the FastAPI layer (main.py) calls.
"""

import os
import time
import json
import logging
from dotenv import load_dotenv

# ────────────────────────────────────────────────────────────
# Imports from local packages
# ────────────────────────────────────────────────────────────
from config import Config, SJ_MORSE_PROFILE
from utils.logging_utils import get_logger, ErrorCollection
from tasks import create_search_tasks, create_extraction_task
from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
from agents import initialize_agents
from tools.scraper_tools import generic_scraper_tool  # for fallback HTML fetch
# (generic_scraper_tool must include the polite User-Agent header patch)

# ────────────────────────────────────────────────────────────
# Global setup
# ────────────────────────────────────────────────────────────
load_dotenv()
Config.configure_logging()
logger = get_logger(__name__)

tools: dict[str, object] = {}
initial_error_collector = ErrorCollection()

try:
    logger.debug("Importing tool wrappers …")
    from tools.search_tools import web_search_tool
    from tools.unified_email_finder import unified_email_finder_tool
    from tools.llm_tools import analyze_pain_points_tool

    tools = {
        "web_search": web_search_tool,
        "generic_scraper": generic_scraper_tool,
        "email_finder": unified_email_finder_tool,
        "pain_point_analyzer": analyze_pain_points_tool,
    }
    logger.info("Global tools dictionary initialised.")

    # Basic sanity checks
    if web_search_tool is None:
        initial_error_collector.add(
            "Tool init", ValueError("web_search_tool failed"), fatal=True
        )

    missing_keys = Config.validate()
    if missing_keys:
        initial_error_collector.add(
            "Configuration",
            ValueError(f"Missing required environment variables: {', '.join(missing_keys)}"),
            fatal=True,
        )

    if initial_error_collector.has_fatal_errors():
        raise RuntimeError(initial_error_collector.get_summary())

    logger.info("Initial global setup checks passed.")

except Exception as e:
    logger.critical("Fatal error during agent_runner setup", exc_info=True)
    raise


# ────────────────────────────────────────────────────────────
# Helper: optional hard-coded URL for debugging
# ────────────────────────────────────────────────────────────
TEST_URL = os.getenv("TEST_URL") or None
if TEST_URL:
    logger.warning(f"[DEBUG] TEST_URL is set → pipeline will scrape {TEST_URL}")


# ────────────────────────────────────────────────────────────
# Main callable
# ────────────────────────────────────────────────────────────
def run_lead_generation_process(selected_segment_names: list | None = None):
    """
    Runs the full agent pipeline.

    Parameters
    ----------
    selected_segment_names : list[str] | None
        If provided, only these segment names from SJ_MORSE_PROFILE
        will be processed.  Pass [] to process none.

    Returns
    -------
    list[dict] | dict
        • On success: list of dicts with keys "name", "website", etc.  
        • On failure / nothing found: dict with 'message' or 'error'.
    """
    logger.info("—" * 20)
    logger.info(f"Starting lead generation | segments={selected_segment_names}")

    # Debug shortcut: scrape a single page then return
    if TEST_URL:
        logger.info(f"[DEBUG] TEST_URL mode – scraping {TEST_URL}")
        try:
            html = generic_scraper_tool(TEST_URL)
            extracted = extract_companies_from_url(
                TEST_URL, {}, {"html": html}  # dummy agents / task
            )
            return extracted or {"message": "No leads extracted from TEST_URL."}
        except Exception as e:
            return {"error": "Cannot access TEST_URL", "details": str(e)}

    # ─── normal run ──────────────────────────────────────────
    run_error_collector = ErrorCollection()
    try:
        agents = initialize_agents(tools, SJ_MORSE_PROFILE)
    except Exception as e:
        return {"error": "Agent init failed", "details": str(e), "processed_companies": []}

    all_segment_cfgs = SJ_MORSE_PROFILE.get("TARGET_SEGMENTS", [])
    if selected_segment_names:
        segments_to_process = [
            cfg for cfg in all_segment_cfgs if cfg["SEGMENT_NAME"] in selected_segment_names
        ]
        if not segments_to_process:
            return {
                "message": "No valid segments selected or found.",
                "selected_segments": selected_segment_names,
                "processed_companies": [],
            }
    else:
        segments_to_process = all_segment_cfgs

    results: list[dict] = []
    processed_websites: set[str] = set()

    for seg_cfg in segments_to_process:
        seg_name = seg_cfg["SEGMENT_NAME"]
        logger.info(f">>> Segment: {seg_name}")

        # 1) create search tasks & perform search ------------------------
        search_tasks = create_search_tasks(agents["research"], seg_cfg)
        url_list = perform_search(agents, search_tasks)
        if not url_list:
            logger.info(f"No URLs found for {seg_name}")
            continue

        urls_to_fetch = url_list[: Config.MAX_URLS_TO_PROCESS]
        for url in urls_to_fetch:
            logger.info(f"Fetching {url}")
            extraction_task = create_extraction_task(url, agents["research"])
            company_dicts = extract_companies_from_url(url, agents, extraction_task)

            for company in company_dicts:
                name = company.get("name")
                website = company.get("website", "").lower().replace("www.", "").rstrip("/")
                if not name or not website or website in processed_websites:
                    continue

                processed_websites.add(website)
                results.append(company)

            time.sleep(0.5)

    if results:
        logger.info(f"Pipeline done – {len(results)} leads.")
        return results
    else:
        logger.info("Pipeline finished but no leads extracted.")
        return {"message": "No leads found.", "processed_companies": []}


# ────────────────────────────────────────────────────────────
# Local test
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    leads = run_lead_generation_process()
    print(json.dumps(leads, indent=2))
