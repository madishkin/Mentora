from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class Question(BaseModel):
    question: str
    options: List[str]
    correct_answer: int
    explanation: str = Field(..., min_length=1, description="1-2 sentence explanation of why the correct answer is right")

    @field_validator("explanation", mode="before")
    @classmethod
    def strip_explanation(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

class AnkiCard(BaseModel):
    front: str = Field(..., description="Вопрос/термин")
    back: str = Field(..., description="Ответ/определение")
    tags: List[str] = Field(default_factory=list)

class ExternalSource(BaseModel):
    topic: str
    url: str
    description: str
    source_type: str

class MindMapNode(BaseModel):
    title: str
    children: List['MindMapNode'] = []
    description: Optional[str] = None

class PresentationSlide(BaseModel):
    title: str
    points: List[str]
    notes: Optional[str] = None

class ExtendedLectureResponse(BaseModel):
    summary: str
    difficulty_level: DifficultyLevel
    test: List[Question]
    anki_cards: List[AnkiCard]
    external_sources: List[ExternalSource]
    mindmap: MindMapNode
    presentation: List[PresentationSlide]
