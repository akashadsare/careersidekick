"""add submission run timing fields

Revision ID: 0002_submission_run_timing
Revises: 0001_initial
Create Date: 2026-03-16 00:30:00

"""

from alembic import op
import sqlalchemy as sa


revision = '0002_submission_run_timing'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('submission_runs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('submission_runs', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('submission_runs', sa.Column('duration_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('submission_runs', 'duration_ms')
    op.drop_column('submission_runs', 'finished_at')
    op.drop_column('submission_runs', 'started_at')
