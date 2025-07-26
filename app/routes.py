from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import get_db
from .models import Vote
from .schemas import VoteSchema, VoteOut
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import StreamingResponse
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
        existing.action = vote.action  # update existing vote
        existing.timestamp = datetime.utcnow()
    else:
        db.add(Vote(**vote.dict()))  # insert new vote
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

# GET all votes by researcher
@router.get("/votes/researcher/{researcher_id}", response_model=List[VoteOut])
def get_votes_by_researcher(researcher_id: str, db: Session = Depends(get_db)):
    validate_id(researcher_id, "researcher_id")

    votes = db.query(Vote).filter(Vote.researcher_id == researcher_id).all()
    return votes

# Top voted grants
@router.get("/votes/top")
def get_top_grants(limit: int = 10, db: Session = Depends(get_db)):
    likes_agg = func.sum(func.case((Vote.action == "like", 1), else_=0))
    results = (
        db.query(
            Vote.grant_id,
            likes_agg.label("likes"),
            func.sum(func.case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
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
        func.sum(func.case((Vote.action == "like", 1), else_=0)).label("likes"),
        func.sum(func.case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
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
        func.sum(func.case((Vote.action == "like", 1), else_=0)).label("likes")
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
    likes_agg = func.sum(func.case((Vote.action == "like", 1), else_=0))
    top = (
        db.query(
            Vote.grant_id,
            likes_agg.label("likes"),
            func.sum(func.case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
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
