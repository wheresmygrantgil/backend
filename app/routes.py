from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import Vote
from .schemas import VoteSchema
from slowapi import Limiter
from slowapi.util import get_remote_address
import re

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
router.limiter = limiter

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
    return [{"grant_id": v.grant_id, "action": v.action} for v in votes]
