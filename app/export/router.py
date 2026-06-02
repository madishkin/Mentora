from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.generation.models import Job, JobStatus
from app.users.models import User
from app.common.errors import NotFoundError
from app.export.pptx_builder import build_pptx
from app.export.apkg_builder import build_apkg
from app.billing.plans import PLAN_LIMITS

router = APIRouter()

@router.get("/{job_id}/pptx")
async def export_pptx(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan_name = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    limits = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["free"])
    if not limits.get("export_enabled", False):
        raise HTTPException(status_code=403, detail="Экспорт доступен только на платных тарифах")
        
    stmt = select(Job).options(selectinload(Job.document)).where(Job.id == job_id, Job.user_id == user.id)
    job = await db.scalar(stmt)
    
    if not job:
        raise NotFoundError("Job", str(job_id))
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed yet")
        
    result = job.result or {}
    presentation_data = result.get("presentation", [])
    if not presentation_data:
        raise HTTPException(status_code=404, detail="Нет данных для презентации")
        
    doc_title = job.document.original_filename if job.document else "EduCraft Presentation"
    if doc_title.endswith((".pdf", ".docx")):
        doc_title = doc_title.rsplit(".", 1)[0]
        
    pptx_bytes = build_pptx(presentation_data, doc_title)
    
    filename = f"{doc_title}.pptx".replace(" ", "_")
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{job_id}/apkg")
async def export_apkg(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan_name = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    limits = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["free"])
    if not limits.get("export_enabled", False):
        raise HTTPException(status_code=403, detail="Экспорт доступен только на платных тарифах")
        
    stmt = select(Job).options(selectinload(Job.document)).where(Job.id == job_id, Job.user_id == user.id)
    job = await db.scalar(stmt)
    
    if not job:
        raise NotFoundError("Job", str(job_id))
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed yet")
        
    result = job.result or {}
    anki_data = result.get("anki_cards", [])
    if not anki_data:
        raise HTTPException(status_code=404, detail="Нет данных для Anki карточек")
        
    doc_title = job.document.original_filename if job.document else "EduCraft Flashcards"
    if doc_title.endswith((".pdf", ".docx")):
        doc_title = doc_title.rsplit(".", 1)[0]
        
    # Genanki expects lists of dicts directly from our model
    apkg_bytes = build_apkg(anki_data, doc_title)
    
    filename = f"{doc_title}.apkg".replace(" ", "_")
    return Response(
        content=apkg_bytes,
        media_type="application/apkg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
