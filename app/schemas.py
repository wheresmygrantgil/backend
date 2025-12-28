from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from datetime import datetime
from typing import Optional

class VoteSchema(BaseModel):
    grant_id: str
    researcher_id: str   # direct field name, no alias
    action: str          # like or dislike

    model_config = ConfigDict(from_attributes=True)


class VoteOut(VoteSchema):
    timestamp: datetime


# Subscription schemas
class SubscriptionCreate(BaseModel):
    researcher_name: str
    email: EmailStr


class SubscriptionStatus(BaseModel):
    subscribed: bool
    email_hint: Optional[str] = None


class SubscriptionOut(BaseModel):
    id: int
    researcher_name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Researcher request schemas
class ResearcherRequestCreate(BaseModel):
    openalex_id: str
    display_name: str
    institution: Optional[str] = None
    works_count: int = 0
    requester_email: Optional[EmailStr] = None

    @field_validator('requester_email', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == '' or v is None:
            return None
        return v

    @field_validator('institution', mode='before')
    @classmethod
    def empty_institution_to_none(cls, v):
        if v == '' or v is None:
            return None
        return v


class ResearcherRequestOut(BaseModel):
    id: int
    openalex_id: str
    display_name: str
    institution: Optional[str]
    works_count: int
    requester_email: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
