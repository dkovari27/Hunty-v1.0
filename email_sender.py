"""
email_sender.py — Sends the PDF report via Gmail SMTP.

Reads credentials from environment variables:
    GMAIL_ADDRESS      — sender address (your Gmail)
    GMAIL_APP_PASSWORD — Gmail App Password (not your login password)
    REPORT_EMAIL       — recipient; defaults to GMAIL_ADDRESS if not set
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


def send_report(pdf_path: str, new_count: int) -> None:
    """Attach pdf_path and send to REPORT_EMAIL via Gmail SMTP SSL."""
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password   = os.environ["GMAIL_APP_PASSWORD"]
    to_address     = os.environ.get("REPORT_EMAIL", gmail_address)

    subject = f"Hunty — {new_count} new job{'s' if new_count != 1 else ''}"

    msg = MIMEMultipart()
    msg["From"]    = gmail_address
    msg["To"]      = to_address
    msg["Subject"] = subject

    msg.attach(MIMEText(
        f"{new_count} new listing{'s' if new_count != 1 else ''} attached.\n\nHunty",
        "plain",
    ))

    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header(
            "Content-Disposition", "attachment",
            filename=Path(pdf_path).name,
        )
        msg.attach(part)

    logger.info("Sending report to %s via Gmail SMTP…", to_address)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, app_password)
        server.send_message(msg)
    logger.info("Email sent: %s", subject)
