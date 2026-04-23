"""Unit tests for the scraper module — no network calls required."""

import pytest
from src.scraper import AdyenScraper, Job


SAMPLE_API_RESPONSE = [
    {
        "id": "42",
        "title": "Software Engineer - Payments",
        "location": {"name": "Amsterdam"},
        "department": {"name": "Engineering"},
        "absolute_url": "https://careers.adyen.com/vacancies/engineering/42/software-engineer-payments",
    },
    {
        "id": "99",
        "title": "Product Designer",
        "location": "San Francisco",
        "department": "Design",
        "absolute_url": "https://careers.adyen.com/vacancies/design/99/product-designer",
    },
    {
        "id": "101",
        "title": "Senior Software Engineer - Platform",
        "location": "Amsterdam",
        "department": "Engineering",
        "absolute_url": "https://careers.adyen.com/vacancies/engineering/101/senior-software-engineer-platform",
    },
]

SAMPLE_HTML = """
<html><body>
  <ul>
    <li class="vacancy-item">
      <a href="/vacancies/engineering/42/software-engineer">
        <h3 class="vacancy-title">Software Engineer</h3>
        <span class="vacancy-location">Amsterdam</span>
        <span class="vacancy-department">Engineering</span>
      </a>
    </li>
    <li class="vacancy-item">
      <a href="/vacancies/design/99/product-designer">
        <h3 class="vacancy-title">Product Designer</h3>
        <span class="vacancy-location">New York</span>
      </a>
    </li>
  </ul>
</body></html>
"""


@pytest.fixture
def scraper():
    return AdyenScraper(timeout=30, use_playwright=False)


class TestJobKeywordMatching:
    def test_matches_both_keywords(self):
        job = Job(
            id="1",
            title="Software Engineer",
            location="Amsterdam",
            department="Engineering",
            url="https://example.com",
        )
        assert job.matches_keywords(["Software", "Engineer"]) is True

    def test_case_insensitive(self):
        job = Job(id="1", title="software engineer", location="", department="", url="")
        assert job.matches_keywords(["SOFTWARE", "ENGINEER"]) is True

    def test_keyword_in_department(self):
        job = Job(id="1", title="Platform Engineer", location="", department="Software Division", url="")
        assert job.matches_keywords(["Software", "Engineer"]) is True

    def test_missing_one_keyword_fails(self):
        job = Job(id="1", title="Product Designer", location="", department="Design", url="")
        assert job.matches_keywords(["Software", "Engineer"]) is False

    def test_single_keyword(self):
        job = Job(id="1", title="Software Architect", location="", department="", url="")
        assert job.matches_keywords(["Software"]) is True


class TestApiParsing:
    def test_extracts_jobs_from_list(self, scraper):
        jobs = scraper._extract_jobs_from_api(SAMPLE_API_RESPONSE)
        assert len(jobs) == 3

    def test_dict_location_unwrapped(self, scraper):
        jobs = scraper._extract_jobs_from_api(SAMPLE_API_RESPONSE)
        se_job = next(j for j in jobs if j.id == "42")
        assert se_job.location == "Amsterdam"

    def test_string_location_preserved(self, scraper):
        jobs = scraper._extract_jobs_from_api(SAMPLE_API_RESPONSE)
        designer = next(j for j in jobs if j.id == "99")
        assert designer.location == "San Francisco"

    def test_dict_department_unwrapped(self, scraper):
        jobs = scraper._extract_jobs_from_api(SAMPLE_API_RESPONSE)
        se_job = next(j for j in jobs if j.id == "42")
        assert se_job.department == "Engineering"

    def test_url_populated(self, scraper):
        jobs = scraper._extract_jobs_from_api(SAMPLE_API_RESPONSE)
        se_job = next(j for j in jobs if j.id == "42")
        assert se_job.url.startswith("https://")

    def test_wrapped_jobs_key(self, scraper):
        wrapped = {"jobs": SAMPLE_API_RESPONSE, "total": 3}
        jobs = scraper._extract_jobs_from_api(wrapped)
        assert len(jobs) == 3

    def test_empty_list(self, scraper):
        assert scraper._extract_jobs_from_api([]) == []

    def test_non_job_json_ignored(self, scraper):
        assert scraper._extract_jobs_from_api({"status": "ok"}) == []


class TestHtmlParsing:
    def test_parses_vacancy_items(self, scraper):
        jobs = scraper._parse_html(SAMPLE_HTML)
        assert len(jobs) >= 1

    def test_title_extracted(self, scraper):
        jobs = scraper._parse_html(SAMPLE_HTML)
        titles = [j.title for j in jobs]
        assert any("Software Engineer" in t for t in titles)

    def test_url_absolutified(self, scraper):
        jobs = scraper._parse_html(SAMPLE_HTML)
        for job in jobs:
            if job.url:
                assert job.url.startswith("https://")

    def test_empty_html_returns_empty(self, scraper):
        jobs = scraper._parse_html("<html><body></body></html>")
        assert jobs == []
