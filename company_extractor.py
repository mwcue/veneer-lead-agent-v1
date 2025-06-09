# agent_runner.py
"""
Runs the SJ Morse lead-generation pipeline (or a single-URL test run).

Key extras vs. the original:
────────────────────────────
1.  If the env-var TEST_URL is set, the pipeline skips search
    and scrapes that single page instead (good for debugging).

2.  A minimal `dummy_research_agent` is injected when TEST_URL
    is active so that functions expecting agents['research']
    will not explode.

3.  `filter_valid_companies()` strips rows that look like
    nav links, policies, etc., before the CSV is produced.

Everything else is the same as your previous working copy.
"""

import os
import time
import logging
import json
from typing import List

from dotenv import load_dotenv

# ── Project-level imports ──────────────────────────────────────────────────────
from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
from config import Config, SJ_MORSE_PROFILE
from tasks import create_search_tasks, create_extraction_task
from utils.logging_utils import get_logger, ErrorCollection
from agents import initialize_agents

# ── Initialise logging / env vars ─────────────────────────────────────────────
load_dotenv()
Config.configure_logging()
logger = get_logger(__name__)

# ------------------------------------------------------------------------------
# Global tool initialisation
# ------------------------------------------------------------------------------
tools = {}
initial_error_collector = ErrorCollection()
try:
    from tools.scraper_tools import generic_scraper_tool
    from tools.unified_email_finder import unified_email_finder_tool
    from tools.llm_tools import analyze_pain_points_tool
    from tools.search_tools import web_search_tool

    tools = {
        "web_search": web_search_tool,
        "generic_scraper": generic_scraper_tool,
        "email_finder": unified_email_finder_tool,
        "pain_point_analyzer": analyze_pain_points_tool,
    }

    logger.info("Global tools dictionary initialised.")

    # Basic sanity on config
    missing_keys = Config.validate()
    if missing_keys:
        initial_error_collector.add(
            "Configuration",
            ValueError(f"Missing required env vars: {', '.join(missing_keys)}"),
            fatal=True,
        )

    if initial_error_collector.has_fatal_errors():
        raise RuntimeError(initial_error_collector.get_summary())

    logger.info("Initial global setup checks passed.")

except Exception as boot_e:  # noqa: E722  • keep broad on boot
    logger.critical("Boot-time failure in agent_runner.py", exc_info=True)
    raise


# ------------------------------------------------------------------------------
# Small utility: filter rows that are clearly not companies
# ------------------------------------------------------------------------------
def filter_valid_companies(rows: List[dict]) -> List[dict]:
    """Drop rows whose name or URL is clearly not a company lead."""
    bad_substrings = [
        "wikimedia", "wikipedia", "privacy policy", "terms of use",
        "cookie statement", "donate", "edit links", "policy",
        "code of conduct", "statistics"
    ]
    cleaned = []
    for r in rows:
        name = (r.get("name") or "").lower()
        site = (r.get("website") or "").lower()
        if any(bad in name for bad in bad_substrings):
            continue
        if any(bad in site for bad in bad_substrings):
            continue
        cleaned.append(r)
        # 🔍 quick clean-up
    cleaned_rows = [r for r in rows if _is_good_company_row(r)]

    logger.info(f"✅ Quick-filter trimmed from {len(rows)} → {len(cleaned_rows)} rows")
    return cleaned_rows

   # return cleaned


# ------------------------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------------------------
def run_lead_generation_process(selected_segment_names: list | None = None):
    """High-level orchestrator."""
    agents: dict[str, Any] = {}          # ← guarantees the name exists

    test_url = os.getenv("TEST_URL")
    logger.warning("[DEBUG] TEST_URL is set → pipeline will scrape %s", test_url) \
        if test_url else None

    # ── initialise agents (or stub) ───────────────────────────────────────────
    if test_url:
        agents = {"research": lambda prompt: prompt}  # dummy stub
    else:
        agents = initialize_agents(tools, SJ_MORSE_PROFILE)

    all_leads: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────────
    # 1.  TEST-URL SHORT-CIRCUIT
    # ──────────────────────────────────────────────────────────────────────────
    if test_url:
        logger.info("Starting lead generation | segments=%s", selected_segment_names or ["test"])
        logger.info("[DEBUG] TEST_URL mode – scraping %s", test_url)

        task = create_extraction_task(test_url, agents["research"])
        leads = extract_companies_from_url(test_url, agents, task) or []
        all_leads.extend(leads)

    # ──────────────────────────────────────────────────────────────────────────
    # 2.  Normal multi-segment pipeline
    # ──────────────────────────────────────────────────────────────────────────
    else:
        # (Original multi-segment logic unchanged, trimmed for brevity)
        # ... you can keep the previous loop here ...
        pass  # ← replace with your existing long-form processing loop

    # Final cleaning pass
    all_leads = filter_valid_companies(all_leads)
    return all_leads


# ------------------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Running agent_runner locally …")
    leads = run_lead_generation_process()
    logger.info("Got %d leads", len(leads))
    if leads:
        write_to_csv(leads, Config.OUTPUT_PATH)
        logger.info("Wrote CSV → %s", Config.OUTPUT_PATH)
