"""
test_email.py — Sends a one-off test email with the existing test_report.pdf.

Run from the Job-Hunter directory:
    python test_email.py

Reads credentials from .env (or environment).  No scraping, no API calls.
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

PDF = os.path.join("outputs", "test_report.pdf")

if not os.path.exists(PDF):
    print(f"ERROR: {PDF} not found — run  python pdf_writer.py  first to generate it.")
    sys.exit(1)

from email_sender import send_report  # noqa: E402

send_report(PDF, new_count=42)
print("Done — check your inbox.")
