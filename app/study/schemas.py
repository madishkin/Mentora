"""
Study Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FlashcardBase(BaseModel):
    front: str
    back: str


class FlashcardResponse(FlashcardBase):
    id: UUID
    course_id: UUID | None
    document_id: UUID | None
    interval: int
    due_date: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ReviewScore(str, Enum):
    AGAIN = "again"  # Не знаю
    GOOD = "good"    # Знаю


class ReviewRequest(BaseModel):
    score: ReviewScore


class ReviewResponse(BaseModel):
    id: UUID
    interval: int
    due_date: datetime
    
    model_config = ConfigDict(from_attributes=True)
