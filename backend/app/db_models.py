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
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g., "US_CITIZEN", "GREEN_CARD", "NEED_SPONSORSHIP"
    remote_preference: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g., "REMOTE", "HYBRID", "ONSITE"
    target_titles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # e.g., ["Software Engineer", "Fullstack Engineer"]
    target_companies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    salary_floor_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_resume_id: Mapped[int | None] = mapped_column(ForeignKey('resumes.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    resumes: Mapped[list['Resume']] = relationship(back_populates='candidate', foreign_keys='Resume.candidate_id')
    drafts: Mapped[list['ApplicationDraft']] = relationship(back_populates='candidate')
    answers: Mapped[list['CandidateAnswer']] = relationship(back_populates='candidate')


class Resume(Base):
    __tablename__ = 'resumes'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)  # S3 path for file storage
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)  # application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, etc.
    parsed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # extracted name, email, phone, skills, experience, etc.
    parser_used: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g., "affinda", "affinda_fallback"
    parse_confidence: Mapped[float | None] = mapped_column(nullable=True)  # 0.0–1.0
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    candidate: Mapped[CandidateProfile] = relationship(back_populates='resumes', foreign_keys='Resume.candidate_id')


class AnswerLibraryQuestion(Base):
    __tablename__ = 'answer_library_questions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_category: Mapped[str] = mapped_column(String(80), nullable=False)  # e.g., "work_auth", "experience", "culture", "technical"
    portal_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # e.g., ["greenhouse", "lever", "workday"]
    frequency_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=999)  # 1 = most common; helps prioritize
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CandidateAnswer(Base):
    __tablename__ = 'candidate_answers'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'))
    library_question_id: Mapped[int] = mapped_column(ForeignKey('answer_library_questions.id', ondelete='CASCADE'))
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_custom: Mapped[bool] = mapped_column(nullable=False, default=False)  # True if user provided custom answer vs. using template
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    candidate: Mapped[CandidateProfile] = relationship(back_populates='answers')


class JobPosting(Base):
    __tablename__ = 'job_postings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "San Francisco, CA" or "Remote"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full job description text
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # URL e.g., "https://boards.greenhouse.io/..."
    ats_type: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g., "greenhouse", "lever", "workday", "ashby"
    ats_detection_confidence: Mapped[float | None] = mapped_column(nullable=True)  # 0.0–1.0
    is_closed: Mapped[bool] = mapped_column(nullable=False, default=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # When job data was extracted from URL
    discovery_run_id: Mapped[int | None] = mapped_column(ForeignKey('job_discovery_runs.id', ondelete='SET NULL'), nullable=True)  # M1.3: track discovery origin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

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


class DiscoveryRunStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class JobDiscoveryQuery(Base):
    """Stores job search queries for discovery (M1.3)."""

    __tablename__ = 'job_discovery_queries'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'))
    title_query: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "Software Engineer"
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "San Francisco, CA"
    remote_preference: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g., "REMOTE", "HYBRID", "ONSITE"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    runs: Mapped[list['JobDiscoveryRun']] = relationship(back_populates='query')


class JobDiscoveryRun(Base):
    """Tracks job discovery execution runs (M1.3)."""

    __tablename__ = 'job_discovery_runs'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_id: Mapped[int] = mapped_column(ForeignKey('job_discovery_queries.id', ondelete='CASCADE'))
    run_status: Mapped[DiscoveryRunStatus] = mapped_column(
        SAEnum(DiscoveryRunStatus, name='discovery_run_status', native_enum=False),
        nullable=False,
        default=DiscoveryRunStatus.PENDING
    )
    jobs_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Total job URLs found
    jobs_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Successfully imported via M1.2
    jobs_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Filtered as duplicates
    jobs_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Failed to import
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    query: Mapped[JobDiscoveryQuery] = relationship(back_populates='runs')
    imported_jobs: Mapped[list['JobPosting']] = relationship('JobPosting', foreign_keys='JobPosting.discovery_run_id')


class FitScore(Base):
    """Job fit scoring results (M1.4)."""

    __tablename__ = 'fit_scores'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('candidate_profiles.id', ondelete='CASCADE'))
    job_id: Mapped[int] = mapped_column(ForeignKey('job_postings.id', ondelete='CASCADE'))
    
    # Overall score: 0-100
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)  # 'apply', 'review', 'skip'
    
    # Dimension scores (0-100)
    title_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skills_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seniority_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    location_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    salary_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    work_auth_match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Hard blocker flags
    hard_blocker_work_auth: Mapped[bool] = mapped_column(nullable=False, default=False)
    hard_blocker_location: Mapped[bool] = mapped_column(nullable=False, default=False)
    hard_blocker_seniority: Mapped[bool] = mapped_column(nullable=False, default=False)
    
    # Explanation and reasoning
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)  # Human-readable summary
    reasoning_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Detailed reasoning per dimension
    
    # Scoring metadata
    scoring_model: Mapped[str] = mapped_column(String(80), nullable=False, default='llm-v1')  # e.g., 'llm-v1', 'rules-v1'
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    candidate: Mapped[CandidateProfile] = relationship(foreign_keys='FitScore.candidate_id')
    job: Mapped[JobPosting] = relationship(foreign_keys='FitScore.job_id')
