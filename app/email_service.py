"""Email notification service for admin alerts."""

import asyncio
import threading
import os
from email.message import EmailMessage
from datetime import datetime

import aiosmtplib

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "gzeevi25@gmail.com")


async def send_email_async(subject: str, body: str):
    """Send email via Gmail SMTP asynchronously."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Email credentials not configured, skipping notification")
        return

    message = EmailMessage()
    message["From"] = GMAIL_USER
    message["To"] = ADMIN_EMAIL
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=GMAIL_USER,
            password=GMAIL_APP_PASSWORD,
        )
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_notification_background(subject: str, body: str):
    """Fire-and-forget email in background thread."""
    def run():
        asyncio.run(send_email_async(subject, body))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


def build_dashboard_summary(db) -> str:
    """Build plain text dashboard summary."""
    from app.models import Subscription, ResearcherRequest

    sub_count = db.query(Subscription).count()
    req_count = db.query(ResearcherRequest).count()

    recent_subs = db.query(Subscription).order_by(
        Subscription.created_at.desc()
    ).limit(5).all()

    recent_reqs = db.query(ResearcherRequest).order_by(
        ResearcherRequest.created_at.desc()
    ).limit(5).all()

    summary = []
    summary.append("=" * 50)
    summary.append("DASHBOARD SUMMARY")
    summary.append("=" * 50)
    summary.append(f"\nPending Researcher Requests: {req_count}")
    summary.append(f"Total Subscriptions: {sub_count}")

    if recent_reqs:
        summary.append("\n--- Recent Researcher Requests ---")
        for r in recent_reqs:
            summary.append(f"  - {r.display_name} ({r.openalex_id})")

    if recent_subs:
        summary.append("\n--- Recent Subscriptions ---")
        for s in recent_subs:
            summary.append(f"  - {s.researcher_name}: {s.email}")

    summary.append("\n" + "=" * 50)
    return "\n".join(summary)


def notify_new_subscription(researcher_name: str, email: str, db):
    """Send notification for new subscription."""
    subject = f"[WMG] New Subscription: {researcher_name}"

    body = f"""NEW SUBSCRIPTION

Researcher: {researcher_name}
Subscriber: {email}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{build_dashboard_summary(db)}
"""
    send_notification_background(subject, body)


def notify_new_researcher_request(display_name: str, openalex_id: str,
                                   requester_email: str, db):
    """Send notification for new researcher request."""
    subject = f"[WMG] New Researcher Request: {display_name}"

    body = f"""NEW RESEARCHER REQUEST

Researcher: {display_name}
OpenAlex ID: {openalex_id}
Requested by: {requester_email or 'Anonymous'}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{build_dashboard_summary(db)}
"""
    send_notification_background(subject, body)
