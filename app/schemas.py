from pydantic import BaseModel

class VoteSchema(BaseModel):
    grant_id: str
    researcher_id: str
    action: str  # like or dislike


class VoteOut(VoteSchema):
    timestamp: str
