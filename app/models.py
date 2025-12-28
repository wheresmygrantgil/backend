from sqlalchemy import Column, String, DateTime, Integer, func, UniqueConstraint
from .database import Base

class Vote(Base):
    __tablename__ = "votes"
    grant_id = Column(String, primary_key=True)
    researcher_id = Column(String, primary_key=True)
    action = Column(String)  # "like" or "dislike"
    timestamp = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    researcher_name = Column(String, index=True)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint('researcher_name', 'email', name='uq_researcher_email'),)


class ResearcherRequest(Base):
    __tablename__ = "researcher_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    openalex_id = Column(String, unique=True)
    display_name = Column(String, nullable=False)
    institution = Column(String, nullable=True)
    works_count = Column(Integer, default=0)
    requester_email = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
