"""
Documents router — file upload and management.
"""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

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
    )
    db.add(doc)
    await db.commit()

    return {"id": str(doc.id)}
