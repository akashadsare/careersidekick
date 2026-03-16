"""initial schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-03-16 00:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

draft_status_enum = sa.Enum('draft', 'approved', 'submitted', 'failed', name='draft_status', native_enum=False)
run_status_enum = sa.Enum('running', 'completed', 'failed', 'cancelled', name='run_status', native_enum=False)


def upgrade() -> None:
    op.create_table(
        'candidate_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('apply_url', sa.Text(), nullable=True),
        sa.Column('ats_type', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'application_drafts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('job_postings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fit_score', sa.Integer(), nullable=False),
        sa.Column('answers_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cover_note', sa.Text(), nullable=False),
        sa.Column('status', draft_status_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'submission_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('draft_id', sa.Integer(), sa.ForeignKey('application_drafts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('tinyfish_run_id', sa.String(length=120), nullable=True),
        sa.Column('run_status', run_status_enum, nullable=False),
        sa.Column('streaming_url', sa.Text(), nullable=True),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('submission_runs')
    op.drop_table('application_drafts')
    op.drop_table('job_postings')
    op.drop_table('candidate_profiles')
