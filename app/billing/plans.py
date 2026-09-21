from typing import Dict, Any
from app.users.models import SubscriptionPlan

PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    SubscriptionPlan.FREE.value: {
        "allowed_sections": {"summary", "test", "anki_cards"},
        "max_input_chars_per_request": 15_000,   # ~6-8 pages
        "max_generations_per_month": 10,
        "export_enabled": False,
        "truncation_enabled": True,
        "difficulty_selection_enabled": False,
    },
    SubscriptionPlan.STUDENT_PRO.value: {
        "allowed_sections": {"summary", "test", "anki_cards", "mindmap", "sources"},
        "max_input_chars_per_request": 40_000,   # ~20 pages
        "max_generations_per_month": 50,
        "export_enabled": True,
        "truncation_enabled": True,
        "difficulty_selection_enabled": True,
    },
    SubscriptionPlan.TEACHER_PRO.value: {
        "allowed_sections": {"summary", "test", "anki_cards", "mindmap", "presentation", "sources"},
        "max_input_chars_per_request": 80_000,   # ~40 pages
        "max_generations_per_month": 200,
        "export_enabled": True,
        "truncation_enabled": True,
        "difficulty_selection_enabled": True,
    },
}
