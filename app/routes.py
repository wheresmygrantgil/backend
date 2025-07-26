from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import get_db
from .models import Vote
from .schemas import VoteSchema
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import StreamingResponse
import csv
import io
import re

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Validation helper
def validate_id(value: str, name: str):
    if not re.match(r"^[A-Za-z0-9_\-]+$", value):
        raise HTTPException(400, f"Invalid {name}")
    return value

# POST vote (create or update)
@router.post("/vote")
@limiter.limit("5/minute")
def record_vote(vote: VoteSchema, db: Session = Depends(get_db)):
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
    else:
        db.add(Vote(**vote.dict()))  # insert new vote
    db.commit()
    return {"status": "success"}

# DELETE vote
@router.delete("/vote/{grant_id}/{researcher_id}")
@limiter.limit("5/minute")
def delete_vote(grant_id: str, researcher_id: str, db: Session = Depends(get_db)):
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
@router.get("/votes/researcher/{researcher_id}")
def get_votes_by_researcher(researcher_id: str, db: Session = Depends(get_db)):
    validate_id(researcher_id, "researcher_id")

    votes = db.query(Vote).filter(Vote.researcher_id == researcher_id).all()
    return [{"grant_id": v.grant_id, "action": v.action, "timestamp": v.timestamp.isoformat()} for v in votes]

# Top voted grants
@router.get("/votes/top")
def get_top_grants(limit: int = 10, db: Session = Depends(get_db)):
    results = (
        db.query(
            Vote.grant_id,
            func.sum(func.case((Vote.action == "like", 1), else_=0)).label("likes"),
            func.sum(func.case((Vote.action == "dislike", 1), else_=0)).label("dislikes")
        )
        .group_by(Vote.grant_id)
        .order_by(func.sum(func.case((Vote.action == "like", 1), else_=0)).desc())
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
    likes = db.query(func.count()).filter(Vote.grant_id == grant_id, Vote.action == "like").scalar()
    dislikes = db.query(func.count()).filter(Vote.grant_id == grant_id, Vote.action == "dislike").scalar()
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

    votes = db.query(Vote).filter(Vote.researcher_id == researcher_id).order_by(Vote.timestamp.desc()).all()
    total_votes = len(votes)
    likes = sum(v.action == "like" for v in votes)
    dislikes = sum(v.action == "dislike" for v in votes)
    recent_votes = [
        {"grant_id": v.grant_id, "action": v.action, "timestamp": v.timestamp.isoformat()}
        for v in votes
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
    votes = db.query(Vote).all()
    return [
        {
            "grant_id": v.grant_id,
            "researcher_id": v.researcher_id,
            "action": v.action,
            "timestamp": v.timestamp.isoformat(),
        }
        for v in votes
    ]

# Export CSV
@router.get("/votes/export/csv")
def export_csv(db: Session = Depends(get_db)):
    votes = db.query(Vote).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["grant_id", "researcher_id", "action", "timestamp"])
    for v in votes:
        writer.writerow([v.grant_id, v.researcher_id, v.action, v.timestamp.isoformat()])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=votes.csv"})

# Vote trend over time (by day)
@router.get("/votes/trend/{grant_id}")
def vote_trend(grant_id: str, db: Session = Depends(get_db)):
    validate_id(grant_id, "grant_id")
    results = (
        db.query(func.date(Vote.timestamp).label("day"), func.count())
        .filter(Vote.grant_id == grant_id)
        .group_by(func.date(Vote.timestamp))
        .order_by("day")
        .all()
    )
    return [{"day": r.day.isoformat(), "count": r[1]} for r in results]
