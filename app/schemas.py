from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class VoteSchema(BaseModel):
    grant_id: str
    researcher_id: str   # direct field name, no alias
    action: str          # like or dislike

    model_config = ConfigDict(from_attributes=True)


class VoteOut(VoteSchema):
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
