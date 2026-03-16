"""Add job discovery tracking for M1.3.

Revision ID: 0006_job_discovery_tracking
Revises: 0005_job_import_extension
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006_job_discovery_tracking'
down_revision = '0005_job_import_extension'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create job_discovery_queries table
    op.create_table(
        'job_discovery_queries',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('title_query', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('remote_preference', sa.String(80), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_job_discovery_queries_candidate_id', 'job_discovery_queries', ['candidate_id'])
    op.create_index('idx_job_discovery_queries_created_at', 'job_discovery_queries', ['created_at'])

    # Create job_discovery_runs table
    op.create_table(
        'job_discovery_runs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('query_id', sa.Integer(), nullable=False),
        sa.Column('run_status', sa.String(80), nullable=False, server_default='pending'),
        sa.Column('jobs_discovered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jobs_imported', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jobs_duplicate', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jobs_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['query_id'], ['job_discovery_queries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_job_discovery_runs_query_id', 'job_discovery_runs', ['query_id'])
    op.create_index('idx_job_discovery_runs_run_status', 'job_discovery_runs', ['run_status'])
    op.create_index('idx_job_discovery_runs_created_at', 'job_discovery_runs', ['created_at'])

    # Add discovery_run_id column to job_postings
    op.add_column('job_postings', sa.Column('discovery_run_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_job_postings_discovery_run_id',
        'job_postings',
        'job_discovery_runs',
        ['discovery_run_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_job_postings_discovery_run_id', 'job_postings', ['discovery_run_id'])


def downgrade() -> None:
    # Drop index and column from job_postings
    op.drop_index('idx_job_postings_discovery_run_id', table_name='job_postings')
    op.drop_constraint('fk_job_postings_discovery_run_id', 'job_postings', type_='foreignkey')
    op.drop_column('job_postings', 'discovery_run_id')

    # Drop job_discovery_runs
    op.drop_index('idx_job_discovery_runs_created_at', table_name='job_discovery_runs')
    op.drop_index('idx_job_discovery_runs_run_status', table_name='job_discovery_runs')
    op.drop_index('idx_job_discovery_runs_query_id', table_name='job_discovery_runs')
    op.drop_table('job_discovery_runs')

    # Drop job_discovery_queries
    op.drop_index('idx_job_discovery_queries_created_at', table_name='job_discovery_queries')
    op.drop_index('idx_job_discovery_queries_candidate_id', table_name='job_discovery_queries')
    op.drop_table('job_discovery_queries')
