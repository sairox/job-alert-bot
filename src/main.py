"""
Entry point for both local execution and AWS Lambda.

Local usage:
    python -m src.main

Lambda handler:
    Set handler = "src.main.lambda_handler" in your Lambda configuration.
"""

import logging
import sys
from typing import Any, Dict

from .config import load_config
from .notifier import EmailNotifier
from .scraper import AdyenScraper
from .state_manager import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_check(config=None) -> Dict[str, Any]:
    """
    Core check loop — fetch jobs, diff against seen state, email new ones.
    Returns a summary dict suitable for logging or a Lambda response body.
    """
    if config is None:
        config = load_config()

    state = StateManager(config)
    scraper = AdyenScraper(
        timeout=config.request_timeout,
        use_playwright=config.use_playwright,
    )
    notifier = EmailNotifier(config)

    logger.info(
        "Starting job check — keywords: %s | url: %s",
        config.keywords,
        config.target_url,
    )
    state.load()

    # Fetch & filter
    all_jobs = scraper.fetch_jobs()
    matching = [j for j in all_jobs if j.matches_keywords(config.keywords)]
    logger.info(
        "Fetched %d total jobs; %d match keywords %s",
        len(all_jobs),
        len(matching),
        config.keywords,
    )

    # Diff against known state
    new_jobs = [j for j in matching if state.is_new(j.id)]
    logger.info("%d new job(s) to alert on", len(new_jobs))

    if new_jobs:
        notifier.send_new_jobs_alert(new_jobs)
        for job in new_jobs:
            state.mark_seen(job.id)
        state.save()
    else:
        logger.info("No new matching jobs — nothing to send.")

    return {
        "total_fetched": len(all_jobs),
        "matching_keywords": len(matching),
        "new_jobs_alerted": len(new_jobs),
        "new_jobs": [
            {"id": j.id, "title": j.title, "location": j.location, "url": j.url}
            for j in new_jobs
        ],
    }


# ------------------------------------------------------------------
# AWS Lambda entry point
# ------------------------------------------------------------------

def lambda_handler(event: Dict, context: Any) -> Dict[str, Any]:
    try:
        result = run_check()
        logger.info("Check complete: %s", result)
        return {"statusCode": 200, "body": result}
    except Exception as exc:
        logger.exception("Job check failed with unhandled exception")
        return {"statusCode": 500, "body": {"error": str(exc)}}


# ------------------------------------------------------------------
# Local entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    result = run_check()
    logger.info("Done: %s", result)
