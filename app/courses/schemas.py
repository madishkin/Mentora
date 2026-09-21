from datetime import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(..., max_length=256)
    emoji: str = Field("📚", max_length=8)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=256)
    emoji: Optional[str] = Field(None, max_length=8)


class CourseInfo(BaseModel):
    id: uuid.UUID
    name: str
    emoji: str
    document_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseDetail(CourseInfo):
    # This will be populated in router logic
    documents: List[dict] = Field(default_factory=list)

