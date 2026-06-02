"""
Documents router — file upload and management.
"""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.common.errors import InvalidFileTypeError, FileTooLargeError
from app.config import settings
from app.database import get_db
from app.documents.models import Document, DocumentStatus, FileType
from app.users.models import User

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=Dict[str, Any], status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    course_id: Optional[uuid.UUID] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (PDF/DOCX) for later generation."""
    # Check file extension
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ["pdf", "docx"]:
        raise InvalidFileTypeError(["pdf", "docx"])

    file_type = FileType.PDF if ext == "pdf" else FileType.DOCX

    # Check size (quick check based on headers if available, otherwise read)
    # Actually saving it directly to disk
    doc_id = uuid.uuid4()
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{ext}")

    size_bytes = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            if size_bytes > settings.max_file_size_mb * 1024 * 1024:
                os.remove(file_path)
                raise FileTooLargeError(settings.max_file_size_mb)
            buffer.write(chunk)

    doc = Document(
        id=doc_id,
        user_id=user.id,
        original_filename=file.filename,
        file_type=file_type,
        file_size_bytes=size_bytes,
        status=DocumentStatus.UPLOADED,
        course_id=course_id,
    )
    db.add(doc)
    await db.commit()

    return {"id": str(doc.id)}


@router.get("/my", response_model=List[Dict[str, Any]])
async def get_my_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all documents for the current user, including their jobs."""
    stmt = (
        select(Document)
        .options(selectinload(Document.jobs))
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    
    response = []
    for doc in docs:
        doc_jobs = [
            {
                "id": str(j.id),
                "status": j.status.value,
                "created_at": j.created_at.isoformat()
            } for j in sorted(doc.jobs, key=lambda x: x.created_at, reverse=True)
        ]
        response.append({
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "file_type": doc.file_type.value,
            "char_count": doc.char_count,
            "status": doc.status.value,
            "course_id": str(doc.course_id) if doc.course_id else None,
            "created_at": doc.created_at.isoformat(),
            "jobs": doc_jobs
        })
        
    return response


@router.patch("/{document_id}/course", response_model=Dict[str, Any])
async def update_document_course(
    document_id: uuid.UUID,
    course_id: Optional[uuid.UUID] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign or remove a document from a course."""
    doc = await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if course_id:
        from app.courses.models import Course
        course = await db.scalar(
            select(Course).where(Course.id == course_id, Course.user_id == user.id)
        )
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
            
    doc.course_id = course_id
    await db.commit()
    
    return {"id": str(doc.id), "course_id": str(doc.course_id) if doc.course_id else None}
