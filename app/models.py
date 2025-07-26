from sqlalchemy import Column, String, DateTime, func
from .database import Base

class Vote(Base):
    __tablename__ = "votes"
    grant_id = Column(String, primary_key=True)
    researcher_id = Column(String, primary_key=True)
    action = Column(String)  # "like" or "dislike"
    timestamp = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
