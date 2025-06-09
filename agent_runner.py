# agent_runner.py
"""
SJ Morse lead-generation pipeline
────────────────────────────────
• If $TEST_URL is set ➜ scrape only that URL (handy for debugging).
• Otherwise ➜ run the normal multi-segment workflow.
• `filter_valid_companies()` trims obvious nav/policy rows
  before the CSV is written.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, List

from dotenv import load_dotenv

# ── Project imports ──────────────────────────────────────────────────────────
from url_processor import perform_search
from company_extractor import extract_companies_from_url, analyze_company
from output_manager import write_to_csv
from config import Config, SJ_MORSE_PROFILE
from tasks import create_search_tasks, create_extraction_task
from utils.logging_utils import get_logger, ErrorCollection
from agents import initialize_agents

# ── Boot-time setup ──────────────────────────────────────────────────────────
load_dotenv()
Config.configure_logging()
logger = get_logger(__name__)

# ── Tool registry (unchanged) ────────────────────────────────────────────────
tools: dict[str, Any] = {}
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

    # basic sanity
    missing = Config.validate()
    if missing:
        initial_error_collector.add(
            "Configuration",
            ValueError(f"Missing env vars: {', '.join(missing)}"),
            fatal=True,
        )

    if initial_error_collector.has_fatal_errors():
        raise RuntimeError(initial_error_collector.get_summary())

    logger.info("Initial global setup checks passed.")

except Exception:
    logger.critical("Boot-time failure in agent_runner.py", exc_info=True)
    raise


# ─────────────────────────────────────────────────────────────────────────────
# 🔎 Small helper – drop rows that aren’t company leads
# ─────────────────────────────────────────────────────────────────────────────
_BAD_STRINGS = {
    "wikimedia",
    "wikipedia",
    "privacy policy",
    "terms of use",
    "cookie statement",
    "donate",
    "edit links",
    "code of conduct",
    "statistics",
}


def _is_good_company_row(row: dict) -> bool:
    name = (row.get("name") or "").lower()
    url = (row.get("website") or "").lower()
    return not any(bad in name or bad in url for bad in _BAD_STRINGS)


def filter_valid_companies(rows: List[dict]) -> List[dict]:
    cleaned_rows = [r for r in rows if _is_good_company_row(r)]
    logger.info("✅ quick-filter: %d → %d rows", len(rows), len(cleaned_rows))
    return cleaned_rows


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────
def run_lead_generation_process(selected_segment_names: list[str] | None = None) -> list[dict]:
    """
    • With $TEST_URL  ➜ scrape that one page and return leads.
    • Otherwise       ➜ run the full multi-segment pipeline.
    """
    all_leads: list[dict] = []

    test_url = os.getenv("TEST_URL")
    if test_url:
        logger.info("[DEBUG] TEST_URL mode ➜ %s", test_url)
        agents = {"research": lambda prompt: prompt}  # tiny dummy so tasks don’t crash
        task = create_extraction_task(test_url, agents["research"])
        leads = extract_companies_from_url(test_url, agents, task) or []
        all_leads.extend(leads)

    else:
        # ── normal multi-segment run (your previous code) ───────────────
        logger.info("Starting lead generation | segments=%s", selected_segment_names or "ALL")
        agents = initialize_agents(tools, SJ_MORSE_PROFILE)

        # ------------- original long loop -------------
        # keep your existing segment-search-extract-analyze
        # loop here; nothing was changed in that logic
        # ----------------------------------------------

        # (for brevity, not pasted again – use the working copy you
        #  already had for multi-segment processing)

    # final clean-up
    return filter_valid_companies(all_leads)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    leads = run_lead_generation_process()
    logger.info("Got %d leads", len(leads))
    if leads:
        write_to_csv(leads, Config.OUTPUT_PATH)
        logger.info("CSV written → %s", Config.OUTPUT_PATH)
