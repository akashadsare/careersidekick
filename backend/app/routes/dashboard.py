"""M1.8: Applications Dashboard Routes

API endpoints for viewing submission history, analytics, and details.
"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    SubmissionSummaryResponse,
    SubmissionListResponse,
    SubmissionDetailResponse,
    CompanyStatsResponse,
    TimelineResponse,
)
from ..services.dashboard_service import DashboardService

router = APIRouter(tags=['dashboard'])


@router.get('/dashboard/summary', response_model=SubmissionSummaryResponse)
def get_submission_summary(
    candidate_id: int = Query(..., description='Candidate profile ID'),
    days: int = Query(default=30, ge=1, le=365, description='Time window in days'),
    db: Session = Depends(get_db),
) -> SubmissionSummaryResponse:
    """
    Get submission summary statistics for a candidate.

    Args:
        candidate_id: Candidate profile ID
        days: Time window (default 30 days)
        db: SQLAlchemy session

    Returns:
        SubmissionSummaryResponse with counts, rates, and averages

    Status Codes:
        200 OK - Success
        404 Not Found - Candidate not found
    """
    try:
        data = DashboardService.get_submission_summary(candidate_id, db, days)
        return SubmissionSummaryResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Summary lookup failed: {str(e)}')


@router.get('/dashboard/submissions', response_model=SubmissionListResponse)
def list_submissions(
    candidate_id: int = Query(..., description='Candidate profile ID'),
    status: str = Query(default=None, description='Filter by status (draft|approved|submitted|failed)'),
    company: str = Query(default=None, description='Filter by company name (substring)'),
    limit: int = Query(default=20, ge=1, le=100, description='Results per page'),
    offset: int = Query(default=0, ge=0, description='Pagination offset'),
    db: Session = Depends(get_db),
) -> SubmissionListResponse:
    """
    List submissions with filtering and pagination.

    Args:
        candidate_id: Candidate profile ID
        status: Optional status filter
        company: Optional company name filter
        limit: Results per page (max 100)
        offset: Pagination offset
        db: SQLAlchemy session

    Returns:
        SubmissionListResponse with paginated results and total count

    Status Codes:
        200 OK - Success
        400 Bad Request - Invalid status filter
        404 Not Found - Candidate not found
    """
    try:
        submissions, total_count = DashboardService.list_submissions(
            candidate_id=candidate_id,
            db=db,
            status_filter=status,
            company_filter=company,
            limit=limit,
            offset=offset,
        )
        return SubmissionListResponse(
            data=submissions,
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Submissions lookup failed: {str(e)}')


@router.get('/dashboard/submissions/{draft_id}', response_model=SubmissionDetailResponse)
def get_submission_detail(
    draft_id: int = Path(..., description='ApplicationDraft ID'),
    db: Session = Depends(get_db),
) -> SubmissionDetailResponse:
    """
    Get detailed information for a single submission.

    Args:
        draft_id: ApplicationDraft ID
        db: SQLAlchemy session

    Returns:
        SubmissionDetailResponse with all submission info and run history

    Status Codes:
        200 OK - Success
        404 Not Found - Draft not found
    """
    try:
        data = DashboardService.get_submission_detail(draft_id, db)
        return SubmissionDetailResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Detail lookup failed: {str(e)}')


@router.get('/dashboard/company-stats', response_model=CompanyStatsResponse)
def get_company_stats(
    candidate_id: int = Query(..., description='Candidate profile ID'),
    db: Session = Depends(get_db),
) -> CompanyStatsResponse:
    """
    Get submission statistics grouped by company.

    Args:
        candidate_id: Candidate profile ID
        db: SQLAlchemy session

    Returns:
        CompanyStatsResponse with per-company metrics

    Status Codes:
        200 OK - Success
        404 Not Found - Candidate not found
    """
    try:
        stats = DashboardService.get_company_stats(candidate_id, db)
        return CompanyStatsResponse(data=stats)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Company stats lookup failed: {str(e)}')


@router.get('/dashboard/timeline', response_model=TimelineResponse)
def get_timeline(
    candidate_id: int = Query(..., description='Candidate profile ID'),
    days: int = Query(default=30, ge=1, le=365, description='Time window in days'),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    """
    Get timeline of submissions (activity over time).

    Args:
        candidate_id: Candidate profile ID
        days: Time window (default 30 days)
        db: SQLAlchemy session

    Returns:
        TimelineResponse with daily activity counts

    Status Codes:
        200 OK - Success
        404 Not Found - Candidate not found
    """
    try:
        timeline = DashboardService.get_timeline(candidate_id, db, days)
        return TimelineResponse(data=timeline, window_days=days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Timeline lookup failed: {str(e)}')
