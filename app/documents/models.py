from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(512), nullable=False
    )
    file_type: Mapped[FileType] = mapped_column(
        Enum(FileType, name="file_type", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="documents")
    course: Mapped["Course | None"] = relationship("Course", back_populates="documents")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="document", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Document {self.original_filename} ({self.status.value})>"


from app.users.models import User  # noqa: E402, F811
from app.generation.models import Job  # noqa: E402
