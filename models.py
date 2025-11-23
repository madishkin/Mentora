from pydantic import BaseModel, Field
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
    simplified_summary: Optional[str] = None
    advanced_summary: Optional[str] = None
    test: List[Question]
    anki_cards: List[AnkiCard]
    external_sources: List[ExternalSource]
    mindmap: MindMapNode
    presentation: List[PresentationSlide]
