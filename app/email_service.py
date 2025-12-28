"""Email notification service for admin alerts."""

import asyncio
import threading
import os
import logging
from email.message import EmailMessage
from datetime import datetime

import aiosmtplib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_email_async(subject: str, body: str):
    """Send email via Gmail SMTP asynchronously."""
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    logger.info(f"[EMAIL] Attempting to send email: {subject}")
    logger.info(f"[EMAIL] GMAIL_USER configured: {bool(gmail_user)}")
    logger.info(f"[EMAIL] GMAIL_APP_PASSWORD configured: {bool(gmail_password)}")

    if not gmail_user or not gmail_password:
        logger.warning("[EMAIL] Email credentials not configured, skipping notification")
        return

    message = EmailMessage()
    message["From"] = gmail_user
    message["To"] = gmail_user  # Send to self
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=gmail_user,
            password=gmail_password,
        )
        logger.info(f"[EMAIL] Successfully sent email to {gmail_user}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send email: {e}")


def send_notification_background(subject: str, body: str):
    """Fire-and-forget email in background thread."""
    logger.info(f"[EMAIL] Starting background thread for: {subject}")

    def run():
        try:
            asyncio.run(send_email_async(subject, body))
        except Exception as e:
            logger.error(f"[EMAIL] Background thread error: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("[EMAIL] Background thread started")


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
    logger.info(f"[EMAIL] notify_new_subscription called for: {researcher_name}")
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
    logger.info(f"[EMAIL] notify_new_researcher_request called for: {display_name}")
    subject = f"[WMG] New Researcher Request: {display_name}"

    body = f"""NEW RESEARCHER REQUEST

Researcher: {display_name}
OpenAlex ID: {openalex_id}
Requested by: {requester_email or 'Anonymous'}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{build_dashboard_summary(db)}
"""
    send_notification_background(subject, body)
