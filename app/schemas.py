from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class VoteSchema(BaseModel):
    grant_id: str
    researcher_id: str = Field(..., alias="user")
    action: str = Field(..., alias="type")  # like or dislike

    model_config = ConfigDict(allow_population_by_field_name=True)


class VoteOut(VoteSchema):
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
