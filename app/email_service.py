"""Email notification service for admin alerts."""

import threading
import os
import logging
from datetime import datetime

import resend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_EMAIL = "gzeevi25@gmail.com"


def send_email(subject: str, body: str):
    """Send email via Resend API."""
    api_key = os.getenv("RESEND_API_KEY")

    logger.info(f"[EMAIL] Attempting to send email: {subject}")
    logger.info(f"[EMAIL] RESEND_API_KEY configured: {bool(api_key)}")

    if not api_key:
        logger.warning("[EMAIL] RESEND_API_KEY not configured, skipping notification")
        return

    resend.api_key = api_key

    try:
        resend.Emails.send({
            "from": "WMG Notifications <onboarding@resend.dev>",
            "to": ADMIN_EMAIL,
            "subject": subject,
            "text": body,
        })
        logger.info(f"[EMAIL] Successfully sent email to {ADMIN_EMAIL}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send email: {e}")


def send_notification_background(subject: str, body: str):
    """Fire-and-forget email in background thread."""
    logger.info(f"[EMAIL] Starting background thread for: {subject}")

    def run():
        try:
            send_email(subject, body)
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
