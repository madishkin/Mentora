"""add plan and monthly_generations_used

Revision ID: 002_add_plan_and_generations
Revises: 001_initial
Create Date: 2026-05-23 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_plan_and_generations'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('plan', sa.String(length=50), server_default='free', nullable=False))
    op.add_column('user_quotas', sa.Column('monthly_generations_used', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('user_quotas', 'monthly_generations_used')
    op.drop_column('users', 'plan')
