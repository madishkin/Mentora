from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.users.models import User
from app.generation.models import Job, JobStatus
from app.study.models import Flashcard
from app.study.schemas import FlashcardResponse, ReviewRequest, ReviewResponse, ReviewScore

router = APIRouter(tags=["Study"])


@router.post("/import/{job_id}", response_model=dict)
async def import_flashcards(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import generated anki cards from a completed job into the study system.
    """
    # Fetch job
    query = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed")
    if not job.result or "anki_cards" not in job.result:
        raise HTTPException(status_code=400, detail="Job result has no anki_cards")

    # Check if already imported
    check_query = select(Flashcard).where(Flashcard.document_id == job.document_id).limit(1)
    check_result = await db.execute(check_query)
    if check_result.scalar_one_or_none() is not None:
         return {"status": "success", "message": "Cards already imported for this document"}

    # Import cards
    cards_data = job.result["anki_cards"]
    if not cards_data:
        raise HTTPException(status_code=400, detail="No cards found in result")

    await db.refresh(job, ["document"])
    course_id = job.document.course_id

    imported_count = 0
    now = datetime.now(timezone.utc)
    for card_data in cards_data:
        front = card_data.get("front", "")
        back = card_data.get("back", "")
        if not front or not back:
            continue

        flashcard = Flashcard(
            user_id=current_user.id,
            course_id=course_id,
            document_id=job.document_id,
            front=front,
            back=back,
            interval=0,
            ease_factor=2.5,
            due_date=now,
        )
        db.add(flashcard)
        imported_count += 1

    await db.commit()

    return {"status": "success", "imported_count": imported_count}


@router.get("/due", response_model=list[FlashcardResponse])
async def get_all_due_cards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all cards due for review today across all courses."""
    now = datetime.now(timezone.utc)
    query = select(Flashcard).where(
        Flashcard.user_id == current_user.id,
        Flashcard.due_date <= now
    ).order_by(Flashcard.due_date.asc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/courses/{course_id}/due", response_model=list[FlashcardResponse])
async def get_due_cards(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all cards due for review today in a specific course."""
    now = datetime.now(timezone.utc)
    query = select(Flashcard).where(
        Flashcard.course_id == course_id,
        Flashcard.user_id == current_user.id,
        Flashcard.due_date <= now
    ).order_by(Flashcard.due_date.asc())
    
    result = await db.execute(query)
    cards = result.scalars().all()
    
    return cards


@router.post("/cards/{card_id}/review", response_model=ReviewResponse)
async def review_card(
    card_id: UUID,
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a review score for a card to update its spaced repetition state.
    """
    query = select(Flashcard).where(Flashcard.id == card_id, Flashcard.user_id == current_user.id)
    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    now = datetime.now(timezone.utc)

    if request.score == ReviewScore.AGAIN:
        # User doesn't know it. Reset interval, due in 5 minutes.
        card.interval = 0
        card.due_date = now + timedelta(minutes=5)
    elif request.score == ReviewScore.GOOD:
        # User knows it. Increase interval.
        if card.interval == 0:
            card.interval = 1
        else:
            # Simple 2x multiplier
            card.interval = card.interval * 2
        
        card.due_date = now + timedelta(days=card.interval)

    await db.commit()
    await db.refresh(card)

    return card
