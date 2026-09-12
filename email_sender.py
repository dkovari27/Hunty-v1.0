"""
email_sender.py: sends the PDF report via Gmail SMTP.

Reads credentials from environment variables:
    GMAIL_ADDRESS:      sender address (your Gmail)
    GMAIL_APP_PASSWORD: Gmail App Password (not your login password)
    REPORT_EMAIL:       recipient; defaults to GMAIL_ADDRESS if not set
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)


def send_no_jobs_report(stats: dict | None = None) -> None:
    """Send a plain-text 'scraper ran, nothing new' confirmation email."""
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password   = os.environ["GMAIL_APP_PASSWORD"]
    to_address     = os.environ.get("REPORT_EMAIL", gmail_address)

    subject = "Hunty: no new jobs today"

    lines = ["The scraper ran successfully but found no new listings.\n"]
    if stats:
        run_s = stats.get("run_time_s", 0)
        run_str = f"{int(run_s // 60)}m {int(run_s % 60)}s" if run_s >= 60 else f"{int(run_s)}s"
        lines.append(f"Total scraped:  {stats.get('total_scraped', 0)}")
        lines.append(f"Unique jobs:    {stats.get('unique_jobs', 0)}")
        lines.append(f"Already seen:   {stats.get('unique_jobs', 0) - stats.get('new_count', 0)}")
        lines.append(f"Run time:       {run_str}")
    lines.append("\nHunty")

    msg = MIMEMultipart()
    msg["From"]    = gmail_address
    msg["To"]      = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(lines), "plain"))

    logger.info("Sending no-new-jobs confirmation to %s…", to_address)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(gmail_address, app_password)
        server.send_message(msg)
    logger.info("Email sent: %s", subject)


def send_report(pdf_path: str, new_count: int, json_path: str | None = None) -> None:
    """Attach pdf_path (and optionally json_path) and send to REPORT_EMAIL via Gmail SMTP.

    json_path, when given, is the same new-jobs list as the PDF, exported as
    JSON: meant to be pasted/uploaded into a Claude Pro/Sonnet chat for
    manual relevance scoring against your CV, without needing the API.
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password   = os.environ["GMAIL_APP_PASSWORD"]
    to_address     = os.environ.get("REPORT_EMAIL", gmail_address)

    subject = f"Hunty: {new_count} new job{'s' if new_count != 1 else ''}"

    msg = MIMEMultipart()
    msg["From"]    = gmail_address
    msg["To"]      = to_address
    msg["Subject"] = subject

    body = f"{new_count} new listing{'s' if new_count != 1 else ''} attached.\n\nHunty"
    if json_path:
        body = (
            f"{new_count} new listing{'s' if new_count != 1 else ''} attached (PDF + JSON).\n"
            "The JSON has the same jobs in full: paste or upload it into a Claude chat "
            "along with your CV to have it scored for relevance.\n\nHunty"
        )
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header(
            "Content-Disposition", "attachment",
            filename=Path(pdf_path).name,
        )
        msg.attach(part)

    if json_path:
        with open(json_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="json")
            part.add_header(
                "Content-Disposition", "attachment",
                filename=Path(json_path).name,
            )
            msg.attach(part)

    logger.info("Sending report to %s via Gmail SMTP…", to_address)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(gmail_address, app_password)
        server.send_message(msg)
    logger.info("Email sent: %s", subject)
