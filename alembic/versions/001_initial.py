"""Initial schema — users, quotas, documents, jobs, usage_records

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely create ENUMs before mapping them in tables.
    user_role = postgresql.ENUM("admin", "teacher", "student", name="user_role", create_type=False)
    file_type = postgresql.ENUM("pdf", "docx", name="file_type", create_type=False)
    document_status = postgresql.ENUM("uploaded", "processing", "ready", "failed", name="document_status", create_type=False)
    job_status = postgresql.ENUM("queued", "processing", "completed", "failed", name="job_status", create_type=False)

    user_role.create(op.get_bind(), checkfirst=True)
    file_type.create(op.get_bind(), checkfirst=True)
    document_status.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("full_name", sa.String(256), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="student"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # User Quotas
    op.create_table(
        "user_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("daily_token_limit", sa.Integer, nullable=False, server_default="100000"),
        sa.Column("monthly_token_limit", sa.Integer, nullable=False, server_default="2000000"),
        sa.Column("daily_tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("monthly_tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_daily_reset", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_monthly_reset", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_type", file_type, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=True, index=True),
        sa.Column("char_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", document_status, nullable=False, server_default="uploaded"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Jobs
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=True),
        sa.Column("status", job_status, nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Usage Records
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("jobs")
    op.drop_table("documents")
    op.drop_table("user_quotas")
    op.drop_table("users")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS file_type")
    op.execute("DROP TYPE IF EXISTS user_role")
