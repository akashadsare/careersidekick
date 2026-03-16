"""add alert incidents table

Revision ID: 0003_alert_incidents
Revises: 0002_submission_run_timing
Create Date: 2026-03-16 02:10:00

"""

from alembic import op
import sqlalchemy as sa


revision = '0003_alert_incidents'
down_revision = '0002_submission_run_timing'
branch_labels = None
depends_on = None

incident_state_enum = sa.Enum('warning', 'critical', 'muted', 'recovered', name='incident_state', native_enum=False)


def upgrade() -> None:
    op.create_table(
        'alert_incidents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('state', incident_state_enum, nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('alert_incidents')
