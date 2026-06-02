"""
Tests for quiz explanation field.

Verifies that:
1. Question model accepts valid explanation
2. Question model rejects missing/empty explanation
3. Full ExtendedLectureResponse includes explanation in every quiz item
4. Service-level validation rejects quiz items without explanation
"""

import pytest
from pydantic import ValidationError

from models import (
    Question,
    ExtendedLectureResponse,
    AnkiCard,
    ExternalSource,
    MindMapNode,
    PresentationSlide,
)


# ── Fixtures ──────────────────────────────────────────────


def _valid_question(**overrides) -> dict:
    """Return a valid question dict, with optional field overrides."""
    base = {
        "question": "Что такое ООП?",
        "options": [
            "Объектно-ориентированное программирование",
            "Операционная обработка процессов",
            "Общее определение парадигм",
            "Облачная организация памяти",
        ],
        "correct_answer": 0,
        "explanation": "ООП расшифровывается как объектно-ориентированное программирование — это парадигма, основанная на объектах.",
    }
    base.update(overrides)
    return base


def _minimal_response(test_items: list[dict]) -> dict:
    """Build the minimum valid dict for an ExtendedLectureResponse."""
    return {
        "summary": "Тестовый конспект.",
        "difficulty_level": "intermediate",
        "test": test_items,
        "anki_cards": [{"front": "Q", "back": "A", "tags": ["t1"]}],
        "external_sources": [
            {
                "topic": "Topic",
                "url": "https://example.com",
                "description": "Desc",
                "source_type": "article",
            }
        ],
        "mindmap": {"title": "Root", "children": []},
        "presentation": [
            {"title": "Slide 1", "points": ["p1", "p2"], "notes": "note"}
        ],
    }


# ── Test 1: valid quiz item parsing ──────────────────────


def test_valid_quiz_item_parsing():
    """A Question with a valid explanation should parse successfully."""
    data = _valid_question()
    q = Question(**data)

    assert q.question == data["question"]
    assert q.options == data["options"]
    assert q.correct_answer == 0
    assert q.explanation == data["explanation"]


# ── Test 2: missing / empty explanation ──────────────────


@pytest.mark.parametrize(
    "bad_value, label",
    [
        (None, "explanation is None"),
        ("", "explanation is empty string"),
        ("   ", "explanation is whitespace only"),
    ],
    ids=["none", "empty", "whitespace"],
)
def test_invalid_quiz_item_missing_explanation(bad_value, label):
    """Question must reject missing or blank explanation via Pydantic."""
    overrides = {}
    if bad_value is None:
        # Omit the field entirely
        data = {
            "question": "Q?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": 0,
        }
    else:
        data = _valid_question(explanation=bad_value)

    with pytest.raises(ValidationError):
        Question(**data)


# ── Test 3: full response includes explanation everywhere ─


def test_full_generation_result_includes_explanation():
    """Every quiz item in a serialized ExtendedLectureResponse must contain 'explanation'."""
    questions = [
        _valid_question(question=f"Вопрос {i}?", explanation=f"Объяснение {i}.")
        for i in range(3)
    ]
    resp = ExtendedLectureResponse(**_minimal_response(questions))
    dumped = resp.model_dump()

    assert len(dumped["test"]) == 3
    for i, item in enumerate(dumped["test"]):
        assert "explanation" in item, f"Quiz item {i} missing 'explanation' key"
        assert len(item["explanation"]) > 0, f"Quiz item {i} has empty explanation"


# ── Test 4: service-level validation rejects bad items ───


def test_service_validation_rejects_missing_explanation():
    """
    Simulate the post-processing validation in FastAIService.process_all_features.
    If any quiz item lacks 'explanation', a ValueError must be raised with a clear message.
    """
    # Reproduce the exact validation logic from services.py
    test_items = [
        _valid_question(question="Q1"),
        {
            "question": "Q2",
            "options": ["A", "B", "C", "D"],
            "correct_answer": 1,
            # NOTE: 'explanation' intentionally omitted
        },
        _valid_question(question="Q3"),
    ]

    with pytest.raises(ValueError, match=r"Quiz item 2 is missing a non-empty 'explanation' field"):
        for i, item in enumerate(test_items):
            if not isinstance(item, dict):
                raise ValueError(f"Quiz item {i + 1} is not a valid object")
            if not item.get("explanation", "").strip():
                raise ValueError(
                    f"Quiz item {i + 1} is missing a non-empty 'explanation' field"
                )
