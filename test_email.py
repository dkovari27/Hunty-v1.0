"""Quick email test — run on Railway to verify SMTP works."""
from email_sender import send_no_jobs_report

send_no_jobs_report(stats={
    "total_scraped": 42,
    "unique_jobs": 10,
    "new_count": 3,
    "run_time_s": 75,
})
print("Done.")
