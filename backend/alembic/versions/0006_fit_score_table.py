"""Add FitScore table for M1.4 fit scoring.

Revision ID: 0006_fit_score_table
Revises: 0005_job_import_extension
Create Date: 2024-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_fit_score_table'
down_revision = '0005_job_import_extension'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create fit_scores table
    op.create_table(
        'fit_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('overall_score', sa.Integer(), nullable=False),
        sa.Column('recommendation', sa.String(20), nullable=False),
        sa.Column('title_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skills_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('seniority_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('location_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('salary_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('work_auth_match_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hard_blocker_work_auth', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('hard_blocker_location', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('hard_blocker_seniority', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('reasoning_json', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('scoring_model', sa.String(80), nullable=False, server_default='llm-v1'),
        sa.Column('scored_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['job_postings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for common queries
    op.create_index('idx_fit_scores_candidate_id', 'fit_scores', ['candidate_id'])
    op.create_index('idx_fit_scores_job_id', 'fit_scores', ['job_id'])
    op.create_index('idx_fit_scores_recommendation', 'fit_scores', ['recommendation'])
    op.create_index('idx_fit_scores_overall_score', 'fit_scores', ['overall_score'])
    op.create_index('idx_fit_scores_candidate_job', 'fit_scores', ['candidate_id', 'job_id'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_fit_scores_candidate_job', table_name='fit_scores')
    op.drop_index('idx_fit_scores_overall_score', table_name='fit_scores')
    op.drop_index('idx_fit_scores_recommendation', table_name='fit_scores')
    op.drop_index('idx_fit_scores_job_id', table_name='fit_scores')
    op.drop_index('idx_fit_scores_candidate_id', table_name='fit_scores')
    
    # Drop table
    op.drop_table('fit_scores')
