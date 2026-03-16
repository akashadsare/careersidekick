from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PackagePreviewRequest(BaseModel):
    candidate_name: str = Field(..., min_length=1)
    role_title: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    candidate_email: str | None = None
    candidate_location: str | None = None


class TinyFishRunRequest(BaseModel):
    url: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    browser_profile: str = 'lite'
    proxy_config: dict | None = None
    draft_id: int | None = None


class PackagePreviewResponse(BaseModel):
    draft_id: int
    candidate_name: str
    role_title: str
    company_name: str
    fit_score: int
    answers: list[dict]
    cover_note: str


class CandidateCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1)
    email: str | None = None
    location: str | None = None


class CandidateResponse(BaseModel):
    id: int
    full_name: str
    email: str | None
    location: str | None


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    apply_url: str | None = None
    ats_type: str | None = 'unknown'


class JobResponse(BaseModel):
    id: int
    title: str
    company_name: str
    apply_url: str | None
    ats_type: str | None


class DraftResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    fit_score: int
    answers_json: dict
    cover_note: str
    status: Literal['draft', 'approved', 'submitted', 'failed']


class DraftUpdateRequest(BaseModel):
    answers_json: dict | None = None
    cover_note: str | None = None
    status: Literal['draft', 'approved', 'submitted', 'failed'] | None = None


class DraftUpdateResponse(BaseModel):
    id: int
    status: Literal['draft', 'approved', 'submitted', 'failed']
    cover_note: str
    answers_json: dict


class SubmissionRunResponse(BaseModel):
    id: int
    draft_id: int | None
    tinyfish_run_id: str | None
    run_status: Literal['running', 'completed', 'failed', 'cancelled']
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    streaming_url: str | None
    error_message: str | None
    created_at: datetime


class SubmissionRunDetailResponse(SubmissionRunResponse):
    result_json: dict | None


# M1.1 — Candidate Profile Onboarding Models

class ResumeParseData(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    years_experience: int | None = None
    skills: list[str] | None = None
    work_history: list[dict] | None = None
    education: list[dict] | None = None


class ResumeUploadResponse(BaseModel):
    id: int
    file_name: str
    file_size_bytes: int
    mime_type: str
    s3_key: str
    parsed_data: ResumeParseData | None
    parser_used: str | None
    parse_confidence: float | None
    is_primary: bool
    created_at: datetime


class CandidateProfileCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    years_experience: int | None = None
    work_authorization: str | None = None  # "US_CITIZEN", "GREEN_CARD", "NEED_SPONSORSHIP", etc.
    remote_preference: str | None = None  # "REMOTE", "HYBRID", "ONSITE"
    target_titles: list[str] | None = None
    target_companies: list[str] | None = None
    salary_floor_usd: int | None = None
    linkedin_url: str | None = None


class CandidateProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None
    location: str | None
    years_experience: int | None
    work_authorization: str | None
    remote_preference: str | None
    target_titles: list[str]
    target_companies: list[str]
    salary_floor_usd: int | None
    linkedin_url: str | None
    primary_resume_id: int | None
    created_at: datetime
    updated_at: datetime


class CandidateProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    years_experience: int | None = None
    work_authorization: str | None = None
    remote_preference: str | None = None
    target_titles: list[str] | None = None
    target_companies: list[str] | None = None
    salary_floor_usd: int | None = None
    linkedin_url: str | None = None


class AnswerLibraryQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_category: str
    portal_types: list[str]
    frequency_rank: int


class CandidateAnswerResponse(BaseModel):
    id: int
    library_question_id: int
    answer_text: str
    is_custom: bool
    created_at: datetime
    updated_at: datetime


class CandidateAnswerCreateRequest(BaseModel):
    library_question_id: int
    answer_text: str = Field(..., min_length=1)
    is_custom: bool = False


class CandidateAnswersListResponse(BaseModel):
    answers: list[CandidateAnswerResponse]
    total: int
    library_questions: list[AnswerLibraryQuestionResponse]


# Job Import Models (M1.2)


class JobExtractedData(BaseModel):
    """Data extracted from job posting URL."""

    title: str = Field(..., min_length=1, max_length=255)
    company_name: str = Field(..., min_length=1, max_length=255)
    location: str | None = None
    description: str | None = None
    apply_url: str | None = None
    ats_type: str | None = Field(
        None,
        description="Detected ATS type: greenhouse, lever, workday, ashby, or null if unknown"
    )
    ats_detection_confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for ATS detection (0.0-1.0)"
    )
    is_closed: bool = Field(False, description="Whether job posting is closed")


class JobImportRequest(BaseModel):
    """Request to import a job posting from a URL."""

    source_url: str = Field(..., min_length=10, description="Full URL to the job posting")


class JobPostingResponse(BaseModel):
    """Response model for a job posting."""

    id: int
    title: str
    company_name: str
    location: str | None
    description: str | None
    apply_url: str | None
    source_url: str | None
    ats_type: str | None
    ats_detection_confidence: float | None
    is_closed: bool
    extracted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobImportResponse(BaseModel):
    """Response from job import endpoint."""

    job: JobPostingResponse
    is_closed: bool = Field(
        False,
        description="True if job posting is closed; user should be warned"
    )
    ats_type: str | None = Field(
        None,
        description="Detected ATS type if available"
    )
    ats_detection_confidence: float | None = Field(
        None,
        description="Confidence score (0.0-1.0)"
    )
    extraction_errors: list[str] = Field(default_factory=list, description="Any warnings or partial extraction issues")


class SubmissionRunStatusUpdateRequest(BaseModel):
    run_status: Literal['running', 'completed', 'failed', 'cancelled']


class SubmissionRunStatusUpdateResponse(BaseModel):
    id: int
    run_status: Literal['running', 'completed', 'failed', 'cancelled']


class ExecutionHistoryPagination(BaseModel):
    limit: int
    cursor: int | None
    next_cursor: int | None
    has_more: bool
    total_count: int
    sort_direction: Literal['asc', 'desc']


class ExecutionHistoryResponse(BaseModel):
    data: list[SubmissionRunResponse]
    pagination: ExecutionHistoryPagination


class DailyFailureCount(BaseModel):
    day: str
    count: int


class ExecutionMetricsResponse(BaseModel):
    window_days: int
    total_runs: int
    completed_runs: int
    failed_runs: int
    cancelled_runs: int
    running_runs: int
    success_rate: float
    avg_duration_ms: int | None
    failures_by_day: list[DailyFailureCount]


class IncidentEventCreateRequest(BaseModel):
    state: Literal['warning', 'critical', 'muted', 'recovered']
    message: str = Field(..., min_length=1)


class IncidentEventResponse(BaseModel):
    id: int
    state: Literal['warning', 'critical', 'muted', 'recovered']
    message: str
    created_at: datetime


# Job Discovery Models (M1.3)


class JobDiscoveryQueryRequest(BaseModel):
    """Request to start a job discovery search."""

    title_query: str | None = Field(None, max_length=255, description="Job title to search for")
    location: str | None = Field(None, max_length=255, description="Location (e.g., 'San Francisco, CA')")
    remote_preference: str | None = Field(
        None,
        description="Remote preference: REMOTE, HYBRID, ONSITE, or null"
    )


class JobDiscoveryQueryResponse(BaseModel):
    """Stored job discovery search query."""

    id: int
    candidate_id: int
    title_query: str | None
    location: str | None
    remote_preference: str | None
    created_at: datetime


class JobDiscoveryRunResponse(BaseModel):
    """Job discovery run execution details."""

    id: int
    query_id: int
    run_status: str  # pending, running, completed, failed
    jobs_discovered: int
    jobs_imported: int
    jobs_duplicate: int
    jobs_failed: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


class JobDiscoverySummary(BaseModel):
    """Summary of a completed discovery run."""

    query_id: int
    run_id: int
    title_query: str | None
    location: str | None
    jobs_discovered: int
    jobs_imported: int
    jobs_duplicate: int
    jobs_failed: int
    duration_seconds: float | None
    ats_detection_rate: float = Field(description="Percentage of jobs with successful ATS detection (0.0-1.0)")
    top_ats_types: dict[str, int] = Field(description="Count of each ATS type found")
    status: str
    error_message: str | None = None


# Fit Scoring Models (M1.4)


class FitScoreDimensions(BaseModel):
    """Individual dimension scores for a job fit."""

    title_match_score: int = Field(..., ge=0, le=100, description="Title relevance (0-100)")
    skills_match_score: int = Field(..., ge=0, le=100, description="Skills overlap (0-100)")
    seniority_match_score: int = Field(..., ge=0, le=100, description="Experience level match (0-100)")
    location_match_score: int = Field(..., ge=0, le=100, description="Location preference match (0-100)")
    salary_match_score: int = Field(..., ge=0, le=100, description="Salary expectation match (0-100)")
    work_auth_match_score: int = Field(..., ge=0, le=100, description="Work authorization compatibility (0-100)")


class HardBlockers(BaseModel):
    """Hard blocker flags for a job."""

    work_auth: bool = Field(False, description="Work authorization mismatch")
    location: bool = Field(False, description="Location incompatibility")
    seniority: bool = Field(False, description="Seniority level mismatch")

    def has_any_blocker(self) -> bool:
        """Check if any hard blocker is triggered."""
        return self.work_auth or self.location or self.seniority


class FitScoreCalculateRequest(BaseModel):
    """Request to calculate fit score for a candidate-job pair."""

    candidate_id: int = Field(..., description="Candidate profile ID")
    job_id: int = Field(..., description="Job posting ID")


class FitScoreResponse(BaseModel):
    """Response with a job's fit score against a candidate."""

    id: int
    candidate_id: int
    job_id: int
    
    # Overall score and recommendation
    overall_score: int = Field(..., ge=0, le=100)
    recommendation: Literal['apply', 'review', 'skip']
    
    # Dimension scores
    dimensions: FitScoreDimensions
    
    # Hard blockers
    hard_blockers: HardBlockers
    
    # Explanation
    explanation: str | None = Field(None, description="Human-readable score summary")
    reasoning_json: dict | None = Field(None, description="Detailed reasoning per dimension")
    
    # Metadata
    scoring_model: str = Field(default='llm-v1')
    scored_at: datetime


class FitScoreBatchResponse(BaseModel):
    """Response with multiple fit scores for a candidate across jobs."""

    candidate_id: int
    total_jobs_scored: int
    jobs_to_apply: list[FitScoreResponse] = Field(description="Score 75-100, recommendation=apply")
    jobs_to_review: list[FitScoreResponse] = Field(description="Score 50-74, recommendation=review")
    jobs_to_skip: list[FitScoreResponse] = Field(description="Score <50, recommendation=skip")
