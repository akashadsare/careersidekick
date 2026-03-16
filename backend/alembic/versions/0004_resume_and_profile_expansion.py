"""Add resume upload and candidate profile expansion for M1.1

Revision ID: 0004_resume_and_profile_expansion
Revises: 0003_alert_incidents
Create Date: 2026-03-16 08:15:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '0004_resume_and_profile_expansion'
down_revision = '0003_alert_incidents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to candidate_profiles table
    op.add_column('candidate_profiles', sa.Column('phone', sa.String(20), nullable=True))
    op.add_column('candidate_profiles', sa.Column('years_experience', sa.Integer(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('work_authorization', sa.String(80), nullable=True))
    op.add_column('candidate_profiles', sa.Column('remote_preference', sa.String(80), nullable=True))
    op.add_column('candidate_profiles', sa.Column('target_titles', JSONB(), nullable=False, server_default='[]'))
    op.add_column('candidate_profiles', sa.Column('target_companies', JSONB(), nullable=False, server_default='[]'))
    op.add_column('candidate_profiles', sa.Column('salary_floor_usd', sa.Integer(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('linkedin_url', sa.String(255), nullable=True))
    op.add_column('candidate_profiles', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default='now()'))

    # Create resumes table
    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('s3_key', sa.String(500), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(80), nullable=False),
        sa.Column('parsed_data', JSONB(), nullable=True),
        sa.Column('parser_used', sa.String(80), nullable=True),
        sa.Column('parse_confidence', sa.Float(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default='now()'),
    )
    op.create_index('ix_resumes_candidate_id', 'resumes', ['candidate_id'])

    # Create answer_library_questions table
    op.create_table(
        'answer_library_questions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_category', sa.String(80), nullable=False),
        sa.Column('portal_types', JSONB(), nullable=False, server_default='[]'),
        sa.Column('frequency_rank', sa.Integer(), nullable=False, server_default='999'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default='now()'),
    )
    op.create_index('ix_answer_library_questions_category', 'answer_library_questions', ['question_category'])

    # Create candidate_answers table
    op.create_table(
        'candidate_answers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('library_question_id', sa.Integer(), sa.ForeignKey('answer_library_questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default='now()'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default='now()'),
    )
    op.create_index('ix_candidate_answers_candidate_id', 'candidate_answers', ['candidate_id'])
    op.create_index('ix_candidate_answers_library_question_id', 'candidate_answers', ['library_question_id'])

    # Add foreign key to candidate_profiles.primary_resume_id
    op.add_column('candidate_profiles', sa.Column('primary_resume_id', sa.Integer(), sa.ForeignKey('resumes.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    # Remove foreign key and columns from candidate_profiles
    op.drop_constraint('candidate_profiles_primary_resume_id_fkey', 'candidate_profiles', type_='foreignkey')
    op.drop_column('candidate_profiles', 'primary_resume_id')
    op.drop_column('candidate_profiles', 'updated_at')
    op.drop_column('candidate_profiles', 'linkedin_url')
    op.drop_column('candidate_profiles', 'salary_floor_usd')
    op.drop_column('candidate_profiles', 'target_companies')
    op.drop_column('candidate_profiles', 'target_titles')
    op.drop_column('candidate_profiles', 'remote_preference')
    op.drop_column('candidate_profiles', 'work_authorization')
    op.drop_column('candidate_profiles', 'years_experience')
    op.drop_column('candidate_profiles', 'phone')

    # Drop indexes and tables
    op.drop_index('ix_candidate_answers_library_question_id', 'candidate_answers')
    op.drop_index('ix_candidate_answers_candidate_id', 'candidate_answers')
    op.drop_table('candidate_answers')

    op.drop_index('ix_answer_library_questions_category', 'answer_library_questions')
    op.drop_table('answer_library_questions')

    op.drop_index('ix_resumes_candidate_id', 'resumes')
    op.drop_table('resumes')
