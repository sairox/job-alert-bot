"""
Email notification module.

Supports two delivery backends:
  - SMTP  (USE_SES=false, default) — good for local dev / Gmail
  - AWS SES (USE_SES=true)         — recommended for production on AWS
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from .scraper import Job

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, config):
        self.config = config

    def send_new_jobs_alert(self, new_jobs: List[Job]) -> None:
        if not new_jobs:
            return

        count = len(new_jobs)
        subject = (
            f"[Adyen Job Alert] {count} new Software Engineer "
            f"position{'s' if count > 1 else ''} posted"
        )
        html_body = self._build_html(new_jobs)
        text_body = self._build_text(new_jobs)

        if self.config.use_ses:
            self._send_ses(subject, html_body, text_body)
        else:
            self._send_smtp(subject, html_body, text_body)

        logger.info(
            f"Alert sent for {count} new job(s) to {self.config.recipient_email}"
        )

    # ------------------------------------------------------------------
    # Email builders
    # ------------------------------------------------------------------

    def _build_html(self, jobs: List[Job]) -> str:
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p CT")
        count = len(jobs)

        rows = ""
        for job in jobs:
            rows += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #eee;">
                <a href="{job.url}"
                   style="color:#0066cc;font-weight:600;text-decoration:none;">
                  {job.title}
                </a>
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #eee;color:#555;">
                {job.location or "—"}
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #eee;color:#555;">
                {job.department or "—"}
              </td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0"
               style="background:#fff;border-radius:8px;overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);max-width:640px;">

          <!-- Header -->
          <tr>
            <td style="background:#0066ff;padding:24px 32px;">
              <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">
                Adyen Job Alert
              </h1>
              <p style="margin:6px 0 0;color:#cce0ff;font-size:13px;">{timestamp}</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:24px 32px;">
              <p style="margin:0 0 20px;font-size:15px;color:#333;">
                <strong>{count}</strong> new
                <strong>Software Engineer</strong>
                position{'s' if count > 1 else ''} matching your alert:
              </p>

              <table width="100%" cellpadding="0" cellspacing="0"
                     style="border-collapse:collapse;border:1px solid #e8e8e8;
                            border-radius:6px;overflow:hidden;">
                <thead>
                  <tr style="background:#f8f9ff;">
                    <th style="padding:10px 16px;text-align:left;font-size:11px;
                               text-transform:uppercase;color:#888;letter-spacing:.5px;">
                      Position
                    </th>
                    <th style="padding:10px 16px;text-align:left;font-size:11px;
                               text-transform:uppercase;color:#888;letter-spacing:.5px;">
                      Location
                    </th>
                    <th style="padding:10px 16px;text-align:left;font-size:11px;
                               text-transform:uppercase;color:#888;letter-spacing:.5px;">
                      Department
                    </th>
                  </tr>
                </thead>
                <tbody>{rows}
                </tbody>
              </table>

              <p style="margin:24px 0 0;text-align:center;">
                <a href="https://careers.adyen.com/vacancies"
                   style="background:#0066ff;color:#fff;text-decoration:none;
                          padding:12px 28px;border-radius:6px;font-size:14px;
                          font-weight:600;display:inline-block;">
                  View All Adyen Vacancies →
                </a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8f8f8;padding:16px 32px;border-top:1px solid #eee;">
              <p style="margin:0;font-size:11px;color:#aaa;text-align:center;">
                You're receiving this because you set up a Software Engineer job alert
                for Adyen. Checks run daily at 7 AM, 12 PM, and 6 PM CT.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    def _build_text(self, jobs: List[Job]) -> str:
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p CT")
        lines = [
            f"Adyen Job Alert — {timestamp}",
            "=" * 50,
            f"{len(jobs)} new Software Engineer position(s) found:",
            "",
        ]
        for job in jobs:
            lines += [
                f"  Title:      {job.title}",
                f"  Location:   {job.location or '—'}",
                f"  Department: {job.department or '—'}",
                f"  URL:        {job.url}",
                "",
            ]
        lines += [
            "View all vacancies: https://careers.adyen.com/vacancies",
            "",
            "Checks run daily at 7 AM, 12 PM, and 6 PM CT.",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Delivery backends
    # ------------------------------------------------------------------

    def _send_smtp(self, subject: str, html: str, text: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.sender_email
        msg["To"] = self.config.recipient_email
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(self.config.smtp_user, self.config.smtp_password)
            srv.sendmail(
                self.config.sender_email,
                self.config.recipient_email,
                msg.as_string(),
            )

    def _send_ses(self, subject: str, html: str, text: str) -> None:
        import boto3

        client = boto3.client("ses", region_name=self.config.aws_region)
        client.send_email(
            Source=self.config.sender_email,
            Destination={"ToAddresses": [self.config.recipient_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text, "Charset": "UTF-8"},
                    "Html": {"Data": html, "Charset": "UTF-8"},
                },
            },
        )
