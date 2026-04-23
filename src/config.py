import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # Target
    target_url: str = "https://careers.adyen.com/vacancies"
    keywords: List[str] = field(default_factory=lambda: ["Software", "Engineer"])

    # Email recipient
    recipient_email: str = "saiviks81@gmail.com"

    # Sender / SMTP (for local / non-SES usage)
    sender_email: str = os.getenv("SENDER_EMAIL", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")

    # AWS SES (set USE_SES=true in production)
    use_ses: bool = os.getenv("USE_SES", "false").lower() == "true"
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")

    # State persistence
    state_file: str = os.getenv("STATE_FILE", "/tmp/seen_jobs.json")
    use_s3: bool = os.getenv("USE_S3", "false").lower() == "true"
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_key: str = os.getenv("S3_KEY", "job-alert-bot/seen_jobs.json")

    # Scraper behaviour
    use_playwright: bool = os.getenv("USE_PLAYWRIGHT", "true").lower() == "true"
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "60"))


def load_config() -> Config:
    return Config()
