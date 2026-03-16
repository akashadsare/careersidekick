"""Extend JobPosting for M1.2 job import by URL and ATS detection.

Revision ID: 0005_job_import_extension
Revises: 0004_resume_and_profile_expansion
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_job_import_extension'
down_revision = '0004_resume_and_profile_expansion'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to job_postings table
    op.add_column('job_postings', sa.Column('location', sa.String(255), nullable=True))
    op.add_column('job_postings', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('job_postings', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('job_postings', sa.Column('ats_detection_confidence', sa.Float(), nullable=True))
    op.add_column('job_postings', sa.Column('is_closed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('job_postings', sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_postings', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, 
                                             server_default=sa.func.now()))
    
    # Create indexes for common queries
    op.create_index('idx_job_postings_ats_type', 'job_postings', ['ats_type'])
    op.create_index('idx_job_postings_is_closed', 'job_postings', ['is_closed'])
    op.create_index('idx_job_postings_source_url', 'job_postings', ['source_url'], unique=False)
    op.create_index('idx_job_postings_extracted_at', 'job_postings', ['extracted_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_job_postings_extracted_at', table_name='job_postings')
    op.drop_index('idx_job_postings_source_url', table_name='job_postings')
    op.drop_index('idx_job_postings_is_closed', table_name='job_postings')
    op.drop_index('idx_job_postings_ats_type', table_name='job_postings')
    
    # Drop columns
    op.drop_column('job_postings', 'updated_at')
    op.drop_column('job_postings', 'extracted_at')
    op.drop_column('job_postings', 'is_closed')
    op.drop_column('job_postings', 'ats_detection_confidence')
    op.drop_column('job_postings', 'source_url')
    op.drop_column('job_postings', 'description')
    op.drop_column('job_postings', 'location')
