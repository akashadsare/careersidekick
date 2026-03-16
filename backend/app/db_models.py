from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class DraftStatus(str, Enum):
    DRAFT = 'draft'
    APPROVED = 'approved'
    SUBMITTED = 'submitted'
    FAILED = 'failed'


class RunStatus(str, Enum):
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class IncidentState(str, Enum):
    WARNING = 'warning'
    CRITICAL = 'critical'
    MUTED = 'muted'
    RECOVERED = 'recovered'


class CandidateProfile(Base):
    __tablename__ = 'candidate_profiles'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    drafts: Mapped[list['ApplicationDraft']] = relationship(back_populates='candidate')


class JobPosting(Base):
    __tablename__ = 'job_postings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    drafts: Mapped[list['ApplicationDraft']] = relationship(back_populates='job')


class ApplicationDraft(Base):
    __tablename__ = 'application_drafts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'))
    job_id: Mapped[int] = mapped_column(ForeignKey('job_postings.id', ondelete='CASCADE'))
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answers_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cover_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DraftStatus] = mapped_column(
        SAEnum(DraftStatus, name='draft_status', native_enum=False), nullable=False, default=DraftStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    candidate: Mapped[CandidateProfile] = relationship(back_populates='drafts')
    job: Mapped[JobPosting] = relationship(back_populates='drafts')
    runs: Mapped[list['SubmissionRun']] = relationship(back_populates='draft')


class SubmissionRun(Base):
    __tablename__ = 'submission_runs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey('application_drafts.id', ondelete='CASCADE'), nullable=True)
    tinyfish_run_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    run_status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name='run_status', native_enum=False), nullable=False, default=RunStatus.RUNNING
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    streaming_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    draft: Mapped[ApplicationDraft | None] = relationship(back_populates='runs')


class AlertIncident(Base):
    __tablename__ = 'alert_incidents'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    state: Mapped[IncidentState] = mapped_column(
        SAEnum(IncidentState, name='incident_state', native_enum=False), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
