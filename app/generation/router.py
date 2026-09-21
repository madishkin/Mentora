from __future__ import annotations

import os
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.common.errors import NotFoundError
from app.database import get_db
from app.documents.models import Document, DocumentStatus, FileType
from app.generation.models import Job, JobStatus
from app.users.models import User
from app.billing.service import (
    check_quota,
    deduct_tokens,
    increment_generation_count,
    precheck_generation,
)
from services import FastAIService, FileProcessor

router = APIRouter()


def _extract_text(doc: Document) -> str:
    """Extract text from a document file. Uses cached text if available."""
    if doc.extracted_text:
        return doc.extracted_text

    file_path = os.path.join("uploads", f"{doc.id}.{doc.file_type.value}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на сервере")

    if doc.file_type == FileType.PDF:
        text = FileProcessor.extract_text_from_pdf(file_path)
    else:
        text = FileProcessor.extract_text_from_docx(file_path)

    if not text or len(text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Не удалось извлечь достаточный объём текста из документа. "
                   "Убедитесь, что файл содержит текст, а не отсканированные изображения.",
        )

    return text


@router.post("/generate/{document_id}/precheck", response_model=Dict[str, Any])
async def precheck(
    document_id: uuid.UUID,
    requested_sections: Optional[list[str]] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Precheck: tells the client what WILL happen if generation is started.
    Does not create jobs or consume tokens.

    Returns: can_generate, truncation info, available/locked sections, warnings.
    """
    doc = await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if not doc:
        raise NotFoundError("Document", str(document_id))

    # Extract text (or use cached)
    lecture_text = _extract_text(doc)

    # Cache extracted text on first extraction
    if not doc.extracted_text:
        doc.extracted_text = lecture_text
        doc.char_count = len(lecture_text)
        await db.commit()

    req_sec = set(requested_sections) if requested_sections else None
    result = await precheck_generation(db, user, len(lecture_text), req_sec)

    return result.to_dict()


@router.post("/generate/{document_id}", response_model=Dict[str, Any], status_code=202)
async def start_generation(
    document_id: uuid.UUID,
    target_difficulty: Optional[str] = Query(None),
    requested_sections: Optional[list[str]] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start generation for a document. Returns a job_id.

    Validation order (all BEFORE job creation):
      1. Document exists
      2. Extract text
      3. Check token quota
      4. Precheck generation (plan limits, truncation, sections)
      5. → If any check fails: return error, NO job created
      6. Create job
      7. Run generation
      8. Deduct tokens + increment count
    """
    doc = await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if not doc:
        raise NotFoundError("Document", str(document_id))

    # ── Step 1: Extract text ──
    lecture_text = _extract_text(doc)

    # Cache extracted text
    if not doc.extracted_text:
        doc.extracted_text = lecture_text
        doc.char_count = len(lecture_text)

    # ── Step 2: Check token quota ──
    await check_quota(db, user.id)

    # ── Step 3: Precheck generation (plan limits, truncation, sections) ──
    req_sec = set(requested_sections) if requested_sections else None
    precheck = await precheck_generation(db, user, len(lecture_text), req_sec)

    if not precheck.can_generate:
        # Return structured error WITHOUT creating a job
        raise HTTPException(
            status_code=422,
            detail={
                "code": precheck.reason,
                "message": precheck.message,
            },
        )

    # ── Step 4: Apply truncation if needed ──
    text_to_process = lecture_text
    if precheck.truncated:
        text_to_process = lecture_text[:precheck.chars_to_process]

    # Determine allowed sections from precheck
    allowed_sections = precheck.requested_sections_filtered

    # Override difficulty for free plan
    from app.billing.plans import PLAN_LIMITS
    plan_name = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    limits = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["free"])
    if not limits.get("difficulty_selection_enabled", False):
        target_difficulty = None  # Free users get default difficulty

    # ── Step 5: NOW create job (validation passed) ──
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        user_id=user.id,
        document_id=doc.id,
        status=JobStatus.PROCESSING,
    )
    db.add(job)
    await db.commit()

    # ── Step 6: Run generation ──
    try:
        raw_results = await FastAIService.process_all_features(
            text_to_process,
            target_difficulty=target_difficulty,
            allowed_sections=allowed_sections,
        )

        # Add truncation metadata to results
        if precheck.truncated:
            raw_results["_meta"] = {
                "truncated": True,
                "chars_processed": precheck.chars_to_process,
                "chars_total": precheck.document_chars,
                "truncation_message": precheck.truncation_message,
            }

        # Estimate tokens and deduct
        estimated_input_tokens = len(text_to_process) // 4
        estimated_output_tokens = 4000
        total_tokens = estimated_input_tokens + estimated_output_tokens
        await deduct_tokens(db, user.id, total_tokens)
        await increment_generation_count(db, user.id)

        # Save result
        job.status = JobStatus.COMPLETED
        job.result = raw_results
        doc.status = DocumentStatus.READY
        if not doc.extracted_text:
            doc.extracted_text = lecture_text
        doc.char_count = len(lecture_text)
        await db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        doc.status = DocumentStatus.FAILED
        await db.commit()

    return {"job_id": str(job.id)}


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_status(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll job status."""
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job:
        raise NotFoundError("Job", str(job_id))

    return {
        "id": str(job.id),
        "status": job.status.value,
        "result": job.result,
        "error_message": job.error_message,
    }


@router.get("/jobs/{job_id}/result", response_model=Dict[str, Any])
async def get_job_full_result(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full job result for history. Includes document title."""
    stmt = (
        select(Job)
        .options(selectinload(Job.document))
        .where(Job.id == job_id, Job.user_id == user.id)
    )
    job = await db.scalar(stmt)
    if not job:
        raise NotFoundError("Job", str(job_id))

    return {
        "id": str(job.id),
        "status": job.status.value,
        "document_title": job.document.original_filename,
        "result": job.result,
    }

