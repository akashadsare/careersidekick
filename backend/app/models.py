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
