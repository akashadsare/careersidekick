"""Fit scoring API routes for M1.4."""

import logging
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import FitScore, CandidateProfile, JobPosting
from app.models import (
    FitScoreCalculateRequest,
    FitScoreResponse,
    FitScoreBatchResponse,
    FitScoreDimensions,
    HardBlockers,
)
from app.services.fit_scorer import FitScoringEngine

logger = logging.getLogger(__name__)

router = APIRouter()
scoring_engine = FitScoringEngine()


def _fit_score_to_response(fit_score: FitScore) -> FitScoreResponse:
    """Convert FitScore ORM model to response schema."""
    reasoning = fit_score.reasoning_json or {}
    
    return FitScoreResponse(
        id=fit_score.id,
        candidate_id=fit_score.candidate_id,
        job_id=fit_score.job_id,
        overall_score=fit_score.overall_score,
        recommendation=fit_score.recommendation,
        dimensions=FitScoreDimensions(
            title_match_score=fit_score.title_match_score,
            skills_match_score=fit_score.skills_match_score,
            seniority_match_score=fit_score.seniority_match_score,
            location_match_score=fit_score.location_match_score,
            salary_match_score=fit_score.salary_match_score,
            work_auth_match_score=fit_score.work_auth_match_score,
        ),
        hard_blockers=HardBlockers(
            work_auth=fit_score.hard_blocker_work_auth,
            location=fit_score.hard_blocker_location,
            seniority=fit_score.hard_blocker_seniority,
        ),
        explanation=fit_score.explanation,
        reasoning_json=reasoning,
        scoring_model=fit_score.scoring_model,
        scored_at=fit_score.scored_at,
    )


@router.post(
    '/fit-scores',
    response_model=FitScoreResponse,
    summary='Calculate fit score for candidate-job pair',
)
async def calculate_fit_score(
    request: FitScoreCalculateRequest,
    db: Session = Depends(get_db)
) -> FitScoreResponse:
    """
    Calculate fit score for a candidate-job pair (M1.4).

    **Scoring Dimensions:**
    - Title Match (0-100): Relevance of job title to candidate's target roles
    - Skills Match (0-100): Overlap between job requirements and candidate skills
    - Seniority Match (0-100): Experience level compatibility
    - Location Match (0-100): Work location preference alignment
    - Salary Match (0-100): Compensation expectation fit
    - Work Auth Match (0-100): Work authorization compatibility

    **Recommendations:**
    - `apply` (75-100): Strong match, candidate should apply
    - `review` (50-74): Moderate match, worth considering
    - `skip` (<50): Poor match, likely to be rejected or frustrating

    **Hard Blockers:**
    - Work Authorization Mismatch: Job requires sponsorship but candidate cannot work
    - Location Incompatibility: Candidate wants remote, job is onsite only
    - Seniority Mismatch: Large experience gap (e.g., 20+ years required but candidate has 3)

    Args:
        request: Candidate ID and Job ID
        db: Database session

    Returns:
        FitScoreResponse with scores, dimensions, and recommendation

    Raises:
        HTTPException 404: Candidate or job not found
    """
    candidate_id = request.candidate_id
    job_id = request.job_id

    # Fetch candidate and job
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f'Candidate {candidate_id} not found')

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f'Job {job_id} not found')

    # Check if score already exists
    existing_score = db.query(FitScore).filter(
        FitScore.candidate_id == candidate_id,
        FitScore.job_id == job_id
    ).first()

    if existing_score:
        logger.info(f'Returning cached fit score for candidate {candidate_id}, job {job_id}')
        return _fit_score_to_response(existing_score)

    # Calculate score
    logger.info(f'Calculating fit score for candidate {candidate_id}, job {job_id}')
    score_result = scoring_engine.calculate_fit_score(candidate, job)

    # Store in database
    fit_score = FitScore(
        candidate_id=candidate_id,
        job_id=job_id,
        overall_score=score_result['overall_score'],
        recommendation=score_result['recommendation'],
        title_match_score=score_result['dimensions']['title_match_score'],
        skills_match_score=score_result['dimensions']['skills_match_score'],
        seniority_match_score=score_result['dimensions']['seniority_match_score'],
        location_match_score=score_result['dimensions']['location_match_score'],
        salary_match_score=score_result['dimensions']['salary_match_score'],
        work_auth_match_score=score_result['dimensions']['work_auth_match_score'],
        hard_blocker_work_auth=score_result['hard_blockers']['work_auth'],
        hard_blocker_location=score_result['hard_blockers']['location'],
        hard_blocker_seniority=score_result['hard_blockers']['seniority'],
        explanation=score_result['explanation'],
        reasoning_json=score_result['reasoning_json'],
        scored_at=datetime.now(UTC),
    )

    db.add(fit_score)
    db.commit()
    db.refresh(fit_score)

    logger.info(
        f'Fit score calculated: {fit_score.id} '
        f'(candidate={candidate_id}, job={job_id}, score={fit_score.overall_score}, '
        f'rec={fit_score.recommendation})'
    )

    return _fit_score_to_response(fit_score)


@router.get(
    '/fit-scores/candidate/{candidate_id}',
    response_model=FitScoreBatchResponse,
    summary='Get fit scores for candidate across all jobs',
)
async def get_candidate_fit_scores(
    candidate_id: int,
    limit: int = Query(50, ge=1, le=500),
    min_score: int = Query(0, ge=0, le=100),
    recommendation: str | None = Query(None),
    db: Session = Depends(get_db)
) -> FitScoreBatchResponse:
    """
    Get all fit scores for a candidate across their discovered/imported jobs.

    Args:
        candidate_id: Candidate profile ID
        limit: Maximum number of jobs per category
        min_score: Filter to scores >= min_score
        recommendation: Filter by recommendation type (apply, review, skip)
        db: Database session

    Returns:
        FitScoreBatchResponse grouped by recommendation and sorted by score
    """
    # Verify candidate exists
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f'Candidate {candidate_id} not found')

    # Fetch fit scores
    query = db.query(FitScore).filter(FitScore.candidate_id == candidate_id)

    if min_score > 0:
        query = query.filter(FitScore.overall_score >= min_score)

    if recommendation:
        query = query.filter(FitScore.recommendation == recommendation)

    all_scores = query.order_by(FitScore.overall_score.desc()).all()

    # Group by recommendation
    apply_jobs = [_fit_score_to_response(s) for s in all_scores if s.recommendation == 'apply'][:limit]
    review_jobs = [_fit_score_to_response(s) for s in all_scores if s.recommendation == 'review'][:limit]
    skip_jobs = [_fit_score_to_response(s) for s in all_scores if s.recommendation == 'skip'][:limit]

    return FitScoreBatchResponse(
        candidate_id=candidate_id,
        total_jobs_scored=len(all_scores),
        jobs_to_apply=apply_jobs,
        jobs_to_review=review_jobs,
        jobs_to_skip=skip_jobs,
    )


@router.get(
    '/fit-scores/{fit_score_id}',
    response_model=FitScoreResponse,
    summary='Get specific fit score',
)
async def get_fit_score(
    fit_score_id: int,
    db: Session = Depends(get_db)
) -> FitScoreResponse:
    """
    Retrieve a specific fit score by ID.

    Args:
        fit_score_id: Fit score record ID
        db: Database session

    Returns:
        FitScoreResponse with full scoring details

    Raises:
        HTTPException 404: Fit score not found
    """
    fit_score = db.query(FitScore).filter(FitScore.id == fit_score_id).first()

    if not fit_score:
        raise HTTPException(status_code=404, detail=f'Fit score {fit_score_id} not found')

    return _fit_score_to_response(fit_score)


@router.delete(
    '/fit-scores/{fit_score_id}',
    summary='Delete fit score cache (will recalculate on next request)',
)
async def delete_fit_score(
    fit_score_id: int,
    db: Session = Depends(get_db)
) -> dict[str, str]:
    """
    Delete a cached fit score to force recalculation.

    Args:
        fit_score_id: Fit score record ID
        db: Database session

    Returns:
        Confirmation message
    """
    fit_score = db.query(FitScore).filter(FitScore.id == fit_score_id).first()

    if not fit_score:
        raise HTTPException(status_code=404, detail=f'Fit score {fit_score_id} not found')

    db.delete(fit_score)
    db.commit()

    logger.info(f'Fit score {fit_score_id} deleted')

    return {'message': f'Fit score {fit_score_id} deleted successfully'}
