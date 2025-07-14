from datetime import datetime

from google.cloud.firestore_v1.base_collection import _auto_id
from pydantic import BaseModel, Field


class Model(BaseModel):
    id: str = Field(default_factory=_auto_id)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
