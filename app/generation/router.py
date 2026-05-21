"""
Generation router — starting background jobs and polling status.
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.common.errors import NotFoundError
from app.database import get_db
from app.documents.models import Document, DocumentStatus, FileType
from app.generation.models import Job, JobStatus
from app.users.models import User
from app.billing.service import check_quota, deduct_tokens
from services import FastAIService, FileProcessor

router = APIRouter()

@router.post("/generate/{document_id}", response_model=Dict[str, Any], status_code=202)
async def start_generation(
    document_id: uuid.UUID,
    target_difficulty: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start generation for a document. Returns a job_id."""
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    if not doc:
        raise NotFoundError("Document", str(document_id))

    # Create a job record
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        user_id=user.id,
        document_id=doc.id,
        status=JobStatus.PROCESSING,
    )
    db.add(job)
    await db.commit()

    # СИНХРОННАЯ ОБРАБОТКА (ВМЕСТО ФОНОВОЙ ДЛЯ БЫСТРОГО РЕШЕНИЯ)
    try:
        # 1. Проверяем квоты перед стартом
        await check_quota(db, user.id)

        # 2. Извлекаем текст
        file_path = os.path.join("uploads", f"{doc.id}.{doc.file_type.value}")
        if not os.path.exists(file_path):
            raise Exception("Файл не найден на сервере")
            
        if doc.file_type == FileType.PDF:
            lecture_text = FileProcessor.extract_text_from_pdf(file_path)
        else:
            lecture_text = FileProcessor.extract_text_from_docx(file_path)
            
        if not lecture_text or len(lecture_text.strip()) < 100:
            raise Exception("Текст слишком короткий или не удалось извлечь")
            
        # 3. Генерируем реальные данные
        raw_results = await FastAIService.process_all_features(
            lecture_text,
            target_difficulty=target_difficulty
        )
        
        # 4. Вычисляем примерное количество потраченных токенов (1 токен ~ 4 символа)
        estimated_input_tokens = len(lecture_text) // 4
        estimated_output_tokens = 4000 # В среднем нейросеть отдает ~4к токенов на все материалы
        total_tokens = estimated_input_tokens + estimated_output_tokens

        # Списываем токены
        await deduct_tokens(db, user.id, total_tokens)

        # 5. Сохраняем результат
        job.status = JobStatus.COMPLETED
        job.result = raw_results
        doc.status = DocumentStatus.READY
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
