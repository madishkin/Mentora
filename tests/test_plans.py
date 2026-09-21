import pytest
from unittest.mock import AsyncMock, patch

from app.common.errors import (
    MonthlyGenerationLimitExceededError,
    SectionNotAvailableOnPlanError,
    DocumentTooLargeForPlanError,
)
from app.users.models import User, UserQuota, SubscriptionPlan
from app.billing.service import check_generation_limits
from services import FastAIService

class MockUser:
    def __init__(self, plan_value, user_id=1):
        self.id = user_id
        self.plan = plan_value

class MockQuota:
    def __init__(self, used_generations=0):
        self.monthly_generations_used = used_generations

@pytest.fixture
def db_session():
    # We only need it as a dummy pass-through for the mock
    return AsyncMock()

@pytest.mark.asyncio
async def test_free_user_blocked_from_presentation(db_session):
    user = MockUser(SubscriptionPlan.FREE.value)
    
    with patch("app.billing.service.check_quota", return_value=MockQuota()):
        with pytest.raises(SectionNotAvailableOnPlanError) as exc_info:
            await check_generation_limits(db_session, user, text_length=1000, requested_sections={"presentation"})
            
        assert "presentation" in str(exc_info.value.details["requested"])

@pytest.mark.asyncio
async def test_free_user_blocked_by_monthly_limit(db_session):
    user = MockUser(SubscriptionPlan.FREE.value)
    # Free plan limit is 5 generations
    quota = MockQuota(used_generations=5)
    
    with patch("app.billing.service.check_quota", return_value=quota):
        with pytest.raises(MonthlyGenerationLimitExceededError):
            await check_generation_limits(db_session, user, text_length=1000)

@pytest.mark.asyncio
async def test_document_too_large_for_free_plan(db_session):
    user = MockUser(SubscriptionPlan.FREE.value)
    # Free plan limit is 5000 chars
    quota = MockQuota()
    
    with patch("app.billing.service.check_quota", return_value=quota):
        with pytest.raises(DocumentTooLargeForPlanError):
            await check_generation_limits(db_session, user, text_length=6000)

@pytest.mark.asyncio
async def test_teacher_pro_allowed_full_generation(db_session):
    user = MockUser(SubscriptionPlan.TEACHER_PRO.value)
    quota = MockQuota(used_generations=90) # Limit is 100
    
    with patch("app.billing.service.check_quota", return_value=quota):
        # 30,000 chars allowed for teacher, we send 20,000
        sections = await check_generation_limits(
            db_session, 
            user, 
            text_length=20000, 
            requested_sections={"presentation", "mindmap", "test"}
        )
        assert "presentation" in sections
        assert "mindmap" in sections
        assert "test" in sections

@pytest.mark.asyncio
async def test_fast_ai_service_skips_prompt2():
    """Verify FastAIService omits prompt2 if its sections are not allowed."""
    with patch("services.FastAIService._async_openai_call") as mock_openai:
        # We need a mock response for prompt1
        mock_openai.return_value = '{"summary": "test", "test": [{"question": "q?", "options": ["a", "b", "c", "d"], "correct_answer": 0, "explanation": "e"}], "difficulty": {}}'
        
        # Test FREE plan (only summary and test)
        # It shouldn't trigger gather with two prompts, it should run sequentially 1 prompt
        result = await FastAIService.process_all_features(
            "test_text", 
            allowed_sections={"summary", "test"}
        )
        
        # _async_openai_call should have been called exactly once for prompt1
        assert mock_openai.call_count == 1
        
        # And prompt2 results should be empty defaults
        assert result["anki_cards"] == []
        assert result["presentation"] == []
        assert result["external_sources"] == []
