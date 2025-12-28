from fastapi import APIRouter, Depends, HTTPException, Request
from urllib.parse import unquote
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from .database import get_db
from .models import Vote, Subscription, ResearcherRequest
from .schemas import (
    VoteSchema, VoteOut,
    SubscriptionCreate, SubscriptionStatus,
    ResearcherRequestCreate, ResearcherRequestOut
)
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import StreamingResponse, HTMLResponse
import csv
import io
import json
from datetime import datetime
from typing import List
import re

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
router.limiter = limiter  # expose limiter for FastAPI app

# Validation helper
def validate_id(value: str, name: str):
    """Validate grant or researcher identifier."""
    value = unquote(value)
    if name == "researcher_id":
        # allow letters, numbers, spaces, comma, apostrophe and hyphen
        if not re.match(r"^[A-Za-z0-9 ,'-]+$", value):
            raise HTTPException(400, f"Invalid {name}")
    else:
        # grant_id remains restricted to alphanumeric, underscore and hyphen
        if not re.match(r"^[A-Za-z0-9_-]+$", value):
            raise HTTPException(400, f"Invalid {name}")
    return value

# POST vote (create or update)
@router.post("/vote")
@limiter.limit("5/minute")
def record_vote(request: Request, vote: VoteSchema, db: Session = Depends(get_db)):
    validate_id(vote.grant_id, "grant_id")
    validate_id(vote.researcher_id, "researcher_id")

    if vote.action not in ["like", "dislike"]:
        raise HTTPException(400, "Invalid action")

    existing = db.query(Vote).filter(
        Vote.grant_id == vote.grant_id,
        Vote.researcher_id == vote.researcher_id
    ).first()

    if existing:
        existing.action = vote.action
        existing.timestamp = datetime.utcnow()
    else:
        db.add(Vote(**vote.dict()))
    db.commit()
    return {"status": "success"}

# DELETE vote
@router.delete("/vote/{grant_id}/{researcher_id}")
@limiter.limit("5/minute")
def delete_vote(request: Request, grant_id: str, researcher_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")
    validate_id(researcher_id, "researcher_id")

    vote = db.query(Vote).filter(
        Vote.grant_id == grant_id,
        Vote.researcher_id == researcher_id
    ).first()

    if not vote:
        raise HTTPException(404, "Vote not found")

    db.delete(vote)
    db.commit()
    return {"status": "deleted"}

# GET total actions per grant
@router.get("/votes/{grant_id}")
def get_grant_votes(grant_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")

    votes = db.query(Vote).filter(Vote.grant_id == grant_id).all()
    return {
        "grant_id": grant_id,
        "likes": sum(v.action == "like" for v in votes),
        "dislikes": sum(v.action == "dislike" for v in votes)
    }

# Alias for frontend convenience
@router.get("/votes/summary/{grant_id}")
def get_grant_votes_summary(grant_id: str, db: Session = Depends(get_db)):
    return get_grant_votes(grant_id, db)

# GET specific researcher vote on a grant
@router.get("/vote/{grant_id}/{researcher_id}")
def get_researcher_vote(grant_id: str, researcher_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")
    validate_id(researcher_id, "researcher_id")

    vote = db.query(Vote).filter(
        Vote.grant_id == grant_id,
        Vote.researcher_id == researcher_id
    ).first()
    return {"grant_id": grant_id, "researcher_id": researcher_id, "action": vote.action if vote else None}

# Alias for frontend convenience
@router.get("/votes/user/{grant_id}/{researcher_id}")
def get_researcher_vote_alias(grant_id: str, researcher_id: str, db: Session = Depends(get_db)):
    return get_researcher_vote(grant_id, researcher_id, db)

# GET all votes by researcher
@router.get("/votes/researcher/{researcher_id}", response_model=List[VoteOut])
def get_votes_by_researcher(researcher_id: str, db: Session = Depends(get_db)):
    validate_id(researcher_id, "researcher_id")

    votes = db.query(Vote).filter(Vote.researcher_id == researcher_id).all()
    return votes

# Top voted grants
@router.get("/votes/top")
def get_top_grants(limit: int = 10, db: Session = Depends(get_db)):
    likes_agg = func.sum(case((Vote.action == "like", 1), else_=0))
    results = (
        db.query(
            Vote.grant_id,
            likes_agg.label("likes"),
            func.sum(case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
        )
        .group_by(Vote.grant_id)
        .order_by(likes_agg.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "grant_id": r.grant_id,
            "likes": int(r.likes),
            "dislikes": int(r.dislikes)
        }
        for r in results
    ]

# Vote ratio per grant
@router.get("/votes/ratio/{grant_id}")
def vote_ratio(grant_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")
    counts = db.query(
        func.sum(case((Vote.action == "like", 1), else_=0)).label("likes"),
        func.sum(case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
    ).filter(Vote.grant_id == grant_id).one()
    likes = counts.likes or 0
    dislikes = counts.dislikes or 0
    total = likes + dislikes
    like_pct = (likes / total * 100) if total else 0.0
    dislike_pct = (dislikes / total * 100) if total else 0.0
    return {
        "grant_id": grant_id,
        "likes": likes,
        "dislikes": dislikes,
        "like_percentage": like_pct,
        "dislike_percentage": dislike_pct,
    }

# Researcher summary
@router.get("/researcher/{researcher_id}/summary")
def researcher_summary(researcher_id: str, db: Session = Depends(get_db)):
    validate_id(researcher_id, "researcher_id")
    summary_stats = db.query(
        func.count(Vote.action).label("total_votes"),
        func.sum(case((Vote.action == "like", 1), else_=0)).label("likes")
    ).filter(Vote.researcher_id == researcher_id).one()

    total_votes = summary_stats.total_votes or 0
    likes = summary_stats.likes or 0
    dislikes = total_votes - likes

    recent_votes_db = (
        db.query(Vote)
        .filter(Vote.researcher_id == researcher_id)
        .order_by(Vote.timestamp.desc())
        .limit(10)
        .all()
    )
    recent_votes = [
        {"grant_id": v.grant_id, "action": v.action, "timestamp": v.timestamp.isoformat()}
        for v in recent_votes_db
    ]
    return {
        "total_votes": total_votes,
        "likes": likes,
        "dislikes": dislikes,
        "recent_votes": recent_votes,
    }

# Export JSON
@router.get("/votes/export/json")
def export_json(db: Session = Depends(get_db)):
    def iter_votes_json():
        yield b"["
        first = True
        for v in db.query(Vote).yield_per(1000):
            if not first:
                yield b","
            yield json.dumps(
                {
                    "grant_id": v.grant_id,
                    "researcher_id": v.researcher_id,
                    "action": v.action,
                    "timestamp": v.timestamp.isoformat(),
                }
            ).encode()
            first = False
        yield b"]"

    return StreamingResponse(iter_votes_json(), media_type="application/json")

# Export CSV
@router.get("/votes/export/csv")
def export_csv(db: Session = Depends(get_db)):
    def iter_votes_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["grant_id", "researcher_id", "action", "timestamp"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for v in db.query(Vote).yield_per(1000):
            writer.writerow([v.grant_id, v.researcher_id, v.action, v.timestamp.isoformat()])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    headers = {"Content-Disposition": "attachment; filename=votes.csv"}
    return StreamingResponse(iter_votes_csv(), media_type="text/csv", headers=headers)

# Vote trend over time (by day)
@router.get("/votes/trend/{grant_id}")
def vote_trend(grant_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")
    results = (
        db.query(func.date(Vote.timestamp).label("day"), func.count().label("count"))
        .filter(Vote.grant_id == grant_id)
        .group_by(func.date(Vote.timestamp))
        .order_by("day")
        .all()
    )
    return [{"day": str(r.day), "count": r.count} for r in results]

# Lightweight health endpoint with basic stats
@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Total votes
    total_votes = db.query(func.count(Vote.grant_id)).scalar() or 0

    # Unique grants
    unique_grants = db.query(func.count(func.distinct(Vote.grant_id))).scalar() or 0

    # Unique researchers
    unique_researchers = db.query(func.count(func.distinct(Vote.researcher_id))).scalar() or 0

    # Top grant by likes
    likes_agg = func.sum(case((Vote.action == "like", 1), else_=0))
    top = (
        db.query(
            Vote.grant_id,
            likes_agg.label("likes"),
            func.sum(case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
        )
        .group_by(Vote.grant_id)
        .order_by(likes_agg.desc())
        .first()
    )
    top_grant = None
    if top:
        top_grant = {
            "grant_id": top.grant_id,
            "likes": int(top.likes),
            "dislikes": int(top.dislikes)
        }

    # Last vote timestamp
    last_vote = db.query(func.max(Vote.timestamp)).scalar()

    return {
        "status": "ok",
        "total_votes": total_votes,
        "unique_grants": unique_grants,
        "unique_researchers": unique_researchers,
        "top_grant": top_grant,
        "last_vote_timestamp": last_vote.isoformat() if last_vote else None
    }


# ==================== SUBSCRIPTIONS ====================

def mask_email(email: str) -> str:
    """Mask email for privacy, e.g., 'john@example.com' -> 'j***@example.com'"""
    if not email or '@' not in email:
        return None
    local, domain = email.split('@', 1)
    if len(local) <= 1:
        return f"{local[0]}***@{domain}"
    return f"{local[0]}***@{domain}"


@router.get("/subscriptions/{researcher_name}", response_model=SubscriptionStatus)
def check_subscription(researcher_name: str, db: Session = Depends(get_db)):
    """Check if a researcher has any subscriptions."""
    researcher_name = unquote(researcher_name)
    subscription = db.query(Subscription).filter(
        Subscription.researcher_name == researcher_name
    ).first()

    if subscription:
        return SubscriptionStatus(
            subscribed=True,
            email_hint=mask_email(subscription.email)
        )
    return SubscriptionStatus(subscribed=False)


@router.post("/subscriptions")
def create_subscription(sub: SubscriptionCreate, db: Session = Depends(get_db)):
    """Create a new subscription. Rejects duplicates."""
    existing = db.query(Subscription).filter(
        Subscription.researcher_name == sub.researcher_name,
        Subscription.email == sub.email
    ).first()

    if existing:
        return {"status": "already_subscribed", "message": "You are already subscribed for this researcher."}

    new_sub = Subscription(
        researcher_name=sub.researcher_name,
        email=sub.email
    )
    db.add(new_sub)
    db.commit()
    return {"status": "success", "message": "Subscription created successfully."}


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(email: str, researcher: str, db: Session = Depends(get_db)):
    """Unsubscribe from email notifications. Called via link in emails."""
    email = unquote(email)
    researcher = unquote(researcher)

    subscription = db.query(Subscription).filter(
        Subscription.researcher_name == researcher,
        Subscription.email == email
    ).first()

    if subscription:
        db.delete(subscription)
        db.commit()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unsubscribed</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
                .container {{ background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #28a745; }}
                p {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Successfully Unsubscribed</h1>
                <p>You have been unsubscribed from grant notifications for <strong>{researcher}</strong>.</p>
                <p>You will no longer receive emails at <strong>{email}</strong>.</p>
            </div>
        </body>
        </html>
        """
    else:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Not Found</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
                .container { background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #dc3545; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Subscription Not Found</h1>
                <p>No subscription was found for this email and researcher combination.</p>
                <p>You may have already unsubscribed.</p>
            </div>
        </body>
        </html>
        """


# ==================== RESEARCHER REQUESTS ====================

@router.post("/researcher-requests")
def create_researcher_request(req: ResearcherRequestCreate, db: Session = Depends(get_db)):
    """Submit a request to add a new researcher."""
    existing = db.query(ResearcherRequest).filter(
        ResearcherRequest.openalex_id == req.openalex_id
    ).first()

    if existing:
        return {"status": "existing", "message": "This researcher has already been requested."}

    new_req = ResearcherRequest(
        openalex_id=req.openalex_id,
        display_name=req.display_name,
        institution=req.institution,
        works_count=req.works_count,
        requester_email=req.requester_email
    )
    db.add(new_req)
    db.commit()
    return {"status": "success", "message": "Request submitted successfully."}


@router.get("/researcher-requests", response_model=List[ResearcherRequestOut])
def get_researcher_requests(db: Session = Depends(get_db)):
    """Get all pending researcher requests."""
    requests = db.query(ResearcherRequest).order_by(ResearcherRequest.created_at.desc()).all()
    return requests


@router.delete("/researcher-requests/{openalex_id}")
def delete_researcher_request(openalex_id: str, db: Session = Depends(get_db)):
    """Delete a researcher request after it has been processed."""
    openalex_id = unquote(openalex_id)
    req = db.query(ResearcherRequest).filter(
        ResearcherRequest.openalex_id == openalex_id
    ).first()

    if not req:
        raise HTTPException(404, "Researcher request not found")

    db.delete(req)
    db.commit()
    return {"status": "deleted", "message": "Request deleted successfully."}
