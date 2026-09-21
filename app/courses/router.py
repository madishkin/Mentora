from __future__ import annotations

import uuid
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.users.models import User
from app.courses.models import Course
from app.courses.schemas import CourseCreate, CourseUpdate, CourseInfo, CourseDetail
from app.documents.models import Document

router = APIRouter()


@router.post("/", response_model=CourseInfo, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = Course(
        id=uuid.uuid4(),
        user_id=user.id,
        name=data.name,
        emoji=data.emoji,
    )
    db.add(course)
    await db.commit()
    
    return CourseInfo(
        id=course.id,
        name=course.name,
        emoji=course.emoji,
        document_count=0,
        created_at=course.created_at,
    )


@router.get("/", response_model=List[CourseInfo])
async def get_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Course, func.count(Document.id).label("doc_count"))
        .outerjoin(Document, Course.id == Document.course_id)
        .where(Course.user_id == user.id)
        .group_by(Course.id)
        .order_by(Course.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        CourseInfo(
            id=course.id,
            name=course.name,
            emoji=course.emoji,
            document_count=count,
            created_at=course.created_at,
        )
        for course, count in rows
    ]


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Course)
        .options(selectinload(Course.documents).selectinload(Document.jobs))
        .where(Course.id == course_id, Course.user_id == user.id)
    )
    course = await db.scalar(stmt)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    doc_list = []
    for doc in sorted(course.documents, key=lambda d: d.created_at, reverse=True):
        doc_jobs = [
            {
                "id": str(j.id),
                "status": j.status.value,
                "created_at": j.created_at.isoformat()
            } for j in sorted(doc.jobs, key=lambda x: x.created_at, reverse=True)
        ]
        doc_list.append({
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "file_type": doc.file_type.value,
            "char_count": doc.char_count,
            "status": doc.status.value,
            "created_at": doc.created_at.isoformat(),
            "jobs": doc_jobs
        })

    detail = CourseDetail(
        id=course.id,
        name=course.name,
        emoji=course.emoji,
        document_count=len(course.documents),
        created_at=course.created_at,
        documents=doc_list
    )
    return detail


@router.patch("/{course_id}", response_model=CourseInfo)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await db.scalar(select(Course).where(Course.id == course_id, Course.user_id == user.id))
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    if data.name is not None:
        course.name = data.name
    if data.emoji is not None:
        course.emoji = data.emoji
        
    await db.commit()
    
    # Get doc count
    count = await db.scalar(select(func.count(Document.id)).where(Document.course_id == course_id))
    
    return CourseInfo(
        id=course.id,
        name=course.name,
        emoji=course.emoji,
        document_count=count or 0,
        created_at=course.created_at,
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await db.scalar(select(Course).where(Course.id == course_id, Course.user_id == user.id))
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    # course_id on documents will be SET NULL automatically by PostgreSQL 
    # thanks to ondelete="SET NULL" in the foreign key, 
    # but SQLAlchemy needs us to explicitly handle it or rely on DB. 
    # Relying on DB is fine.
    await db.delete(course)
    await db.commit()
