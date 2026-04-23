"""
Scraper for https://careers.adyen.com/vacancies.

Strategy:
  1. Primary  — Playwright headless Chromium, intercepts the underlying JSON
               API call the SPA makes when loading vacancies.
  2. Fallback — If no API payload is captured, parse the rendered HTML.
  3. Last-resort — requests + BeautifulSoup (USE_PLAYWRIGHT=false).
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.adyen.com"
VACANCIES_URL = f"{BASE_URL}/vacancies"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class Job:
    id: str
    title: str
    location: str
    department: str
    url: str

    def matches_keywords(self, keywords: List[str]) -> bool:
        haystack = f"{self.title} {self.department}".lower()
        return all(kw.lower() in haystack for kw in keywords)


class AdyenScraper:
    def __init__(self, timeout: int = 60, use_playwright: bool = True):
        self.timeout = timeout
        self.use_playwright = use_playwright

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_jobs(self) -> List[Job]:
        if self.use_playwright:
            return self._fetch_playwright()
        return self._fetch_requests()

    # ------------------------------------------------------------------
    # Playwright path (primary)
    # ------------------------------------------------------------------

    def _fetch_playwright(self) -> List[Job]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed; falling back to requests.")
            return self._fetch_requests()

        captured: List[Dict] = []

        def _on_response(response):
            """Capture any JSON response that looks like a job list."""
            url = response.url
            if response.status != 200:
                return
            # Target API paths commonly used by career-site SPAs
            if not any(p in url for p in ["/api/", "/vacancies", "/jobs", "/_next/data"]):
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            try:
                data = response.json()
                jobs = self._extract_jobs_from_api(data)
                if jobs:
                    captured.extend(jobs)
                    logger.info(f"Captured {len(jobs)} jobs from API: {url}")
            except Exception:
                pass

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                ],
            )
            ctx = browser.new_context(
                user_agent=_BROWSER_HEADERS["User-Agent"],
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = ctx.new_page()
            page.on("response", _on_response)

            try:
                page.goto(VACANCIES_URL, wait_until="networkidle", timeout=self.timeout * 1000)
                # Give lazy-loaded content a moment to settle
                page.wait_for_timeout(3000)

                if not captured:
                    # Scroll to trigger any lazy loading
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                if captured:
                    # Deduplicate by ID — the page sometimes fires the same
                    # Greenhouse API request twice (pagination + featured section).
                    seen: set = set()
                    unique = []
                    for job in captured:
                        if job.id not in seen:
                            seen.add(job.id)
                            unique.append(job)
                    logger.info(
                        f"API interception: {len(captured)} raw → {len(unique)} unique jobs"
                    )
                    browser.close()
                    return unique

                # Fallback: parse the fully-rendered HTML
                html = page.content()
                browser.close()
                logger.info("No API payload captured; parsing rendered HTML.")
                return self._parse_html(html)

            except Exception as exc:
                logger.error(f"Playwright error: {exc}")
                browser.close()
                raise

    # ------------------------------------------------------------------
    # requests path (fallback / USE_PLAYWRIGHT=false)
    # ------------------------------------------------------------------

    def _fetch_requests(self) -> List[Job]:
        session = requests.Session()
        session.headers.update(_BROWSER_HEADERS)
        try:
            resp = session.get(VACANCIES_URL, timeout=self.timeout)
            resp.raise_for_status()
            return self._parse_html(resp.text)
        except requests.RequestException as exc:
            logger.error(f"HTTP request failed: {exc}")
            raise

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _extract_jobs_from_api(self, data: Any) -> List[Job]:
        """
        Try to extract jobs from whatever JSON shape the API returns.
        Handles: list of jobs, {"jobs": [...]}, {"data": [...]}, etc.
        """
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ("jobs", "vacancies", "positions", "data", "results", "items"):
                if key in data and isinstance(data[key], list):
                    candidates = data[key]
                    break
            else:
                return []
        else:
            return []

        jobs = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            job = self._dict_to_job(item)
            if job:
                jobs.append(job)
        return jobs

    def _dict_to_job(self, item: Dict) -> Optional[Job]:
        """Map a raw API dict to a Job, tolerating varied field names."""
        title = (
            item.get("title")
            or item.get("name")
            or item.get("jobTitle")
            or item.get("job_title")
            or ""
        )
        if not title:
            return None

        job_id = str(
            item.get("id")
            or item.get("requisitionId")
            or item.get("requisition_id")
            or item.get("jobId")
            or re.sub(r"\W+", "-", title.lower())
        )

        # Location — may be a string or a nested object
        loc = item.get("location") or item.get("city") or item.get("office") or {}
        if isinstance(loc, dict):
            loc = loc.get("name") or loc.get("city") or loc.get("label") or ""
        location = str(loc)

        # Department
        dept = item.get("department") or item.get("team") or item.get("category") or {}
        if isinstance(dept, dict):
            dept = dept.get("name") or dept.get("label") or ""
        department = str(dept)

        # URL
        url = (
            item.get("absolute_url")
            or item.get("url")
            or item.get("applyUrl")
            or item.get("apply_url")
            or f"{VACANCIES_URL}/{job_id}"
        )
        if url and not url.startswith("http"):
            url = f"{BASE_URL}{url}"

        return Job(id=job_id, title=title, location=location, department=department, url=url)

    def _parse_html(self, html: str) -> List[Job]:
        """Parse rendered HTML using common career-page CSS patterns."""
        soup = BeautifulSoup(html, "lxml")
        jobs: List[Job] = []

        # Try increasingly broad selectors
        selectors = [
            # Adyen-specific guesses (based on common React career-site patterns)
            "li[class*='vacancy']",
            "div[class*='vacancy']",
            "article[class*='vacancy']",
            "li[class*='job']",
            "div[class*='job-card']",
            "div[class*='position']",
            "div[class*='listing']",
            # Generic broad sweep — anchor tags pointing to job detail pages
            f"a[href*='/vacancies/']",
        ]

        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"Matched {len(cards)} cards with selector: {selector!r}")
                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        jobs.append(job)
                if jobs:
                    break

        if not jobs:
            logger.warning(
                "No job cards found in HTML. "
                "The page may require JavaScript or the CSS selectors need updating. "
                "Enable USE_PLAYWRIGHT=true for JS rendering."
            )

        logger.info(f"Parsed {len(jobs)} jobs from HTML")
        return jobs

    def _parse_card(self, card) -> Optional[Job]:
        try:
            title_el = card.select_one(
                "[class*='title'], [class*='name'], h1, h2, h3, h4"
            ) or card
            title = title_el.get_text(strip=True)
            if not title or len(title) > 200:
                return None

            link = card if card.name == "a" else card.select_one("a")
            url = ""
            if link and link.get("href"):
                href = link["href"]
                url = href if href.startswith("http") else f"{BASE_URL}{href}"

            job_id = url.split("/")[-1] if url else re.sub(r"\W+", "-", title.lower())

            loc_el = card.select_one("[class*='location'], [class*='city'], [class*='place']")
            location = loc_el.get_text(strip=True) if loc_el else ""

            dept_el = card.select_one("[class*='department'], [class*='team'], [class*='category']")
            department = dept_el.get_text(strip=True) if dept_el else ""

            return Job(id=job_id, title=title, location=location, department=department, url=url)
        except Exception as exc:
            logger.debug(f"Skipping card — parse error: {exc}")
            return None
