from pydantic import BaseModel
from datetime import datetime

class VoteSchema(BaseModel):
    grant_id: str
    researcher_id: str
    action: str  # like or dislike


class VoteOut(VoteSchema):
    timestamp: datetime

    class Config:
        orm_mode = True
