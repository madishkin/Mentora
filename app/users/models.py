"""
User & UserQuota ORM models — PostgreSQL native types.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.STUDENT,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    quota: Mapped[UserQuota | None] = relationship(
        "UserQuota", back_populates="user", uselist=False, lazy="selectin"
    )
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="owner", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"


class UserQuota(Base):
    __tablename__ = "user_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    daily_token_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100_000
    )
    monthly_token_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2_000_000
    )
    daily_tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    monthly_tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_daily_reset: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_monthly_reset: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="quota")

    def __repr__(self) -> str:
        return f"<UserQuota user={self.user_id} daily={self.daily_tokens_used}/{self.daily_token_limit}>"


# Forward reference imports (resolved after all models load)
from app.documents.models import Document  # noqa: E402
