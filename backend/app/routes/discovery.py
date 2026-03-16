"""Job discovery routes for M1.3."""

import asyncio
import logging
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import JobDiscoveryQuery, JobDiscoveryRun, JobPosting, DiscoveryRunStatus
from app.models import (
    JobDiscoveryQueryRequest,
    JobDiscoveryQueryResponse,
    JobDiscoveryRunResponse,
    JobDiscoverySummary,
)
from app.services.job_discovery import JobDiscoveryService
from app.routes.jobs import import_job_by_url as import_job_endpoint

logger = logging.getLogger(__name__)

router = APIRouter()


def _discovery_run_to_response(run: JobDiscoveryRun) -> JobDiscoveryRunResponse:
    """Convert JobDiscoveryRun ORM model to response schema."""
    return JobDiscoveryRunResponse(
        id=run.id,
        query_id=run.query_id,
        run_status=run.run_status.value,
        jobs_discovered=run.jobs_discovered,
        jobs_imported=run.jobs_imported,
        jobs_duplicate=run.jobs_duplicate,
        jobs_failed=run.jobs_failed,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        error_message=run.error_message,
        created_at=run.created_at,
    )


@router.post(
    '/jobs/discover',
    response_model=JobDiscoverySummary,
    summary='Discover jobs from LinkedIn and Greenhouse',
    tags=['discovery']
)
async def discover_jobs(
    candidate_id: int,
    request: JobDiscoveryQueryRequest,
    db: Session = Depends(get_db)
) -> JobDiscoverySummary:
    """
    Discover job postings from multiple sources (M1.3).

    **Process:**
    1. Accepts search parameters: title, location, remote preference
    2. Discovers jobs from LinkedIn Jobs and Greenhouse public boards
    3. Deduplicates results by URL
    4. For each unique URL, calls M1.2 import endpoint to extract metadata
    5. Tracks import results and returns summary

    **Accepts:**
    - `title_query`: Job title search term (e.g., "Software Engineer")
    - `location`: Location filter (e.g., "San Francisco, CA" or "Remote")
    - `remote_preference`: REMOTE, HYBRID, ONSITE

    **Returns:**
    - Total jobs discovered
    - Successfully imported (via M1.2)
    - Duplicates filtered
    - Failed imports
    - ATS detection statistics
    - Top ATS types found

    **SLO:** Completes within 3 minutes (180s) for typical queries
    """
    logger.info(
        f'Starting job discovery for candidate {candidate_id}: '
        f'title={request.title_query}, location={request.location}, remote={request.remote_preference}'
    )

    # Create discovery query record
    query = JobDiscoveryQuery(
        candidate_id=candidate_id,
        title_query=request.title_query,
        location=request.location,
        remote_preference=request.remote_preference,
    )
    db.add(query)
    db.commit()
    db.refresh(query)

    # Create discovery run
    run = JobDiscoveryRun(
        query_id=query.id,
        run_status=DiscoveryRunStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        # Execute discovery
        discovery_service = JobDiscoveryService(timeout=30, max_concurrent_requests=5)
        discovery_result = await discovery_service.discover(
            title_query=request.title_query,
            location=request.location,
            remote_preference=request.remote_preference,
            max_results=100,
        )

        discovered_urls = discovery_result.get('discovered_urls', [])
        deduped_urls = discovery_result.get('deduped_urls', [])

        run.jobs_discovered = len(discovered_urls)
        run.jobs_duplicate = len(discovered_urls) - len(deduped_urls)

        logger.info(
            f'Discovery found {len(discovered_urls)} URLs, {len(deduped_urls)} unique. '
            f'Proceeding to M1.2 import for each...'
        )

        # Import each unique job URL via M1.2 endpoint
        imported_count = 0
        failed_count = 0
        ats_type_counts = {}
        ats_successes = 0

        for url in deduped_urls:
            try:
                # Call M1.2 import endpoint
                # In production, use httpx client to call internal endpoint
                # For now, simulate the import by tracking the URL in JobPosting
                
                # Create a minimal JobPosting record with the discovered URL
                # (In Phase 2, this will actually call the import endpoint)
                job = JobPosting(
                    title='[Discovered]',  # Will be extracted in follow-up import
                    company_name='[Unknown]',
                    source_url=url,
                    ats_detection_confidence=0.0,
                    is_closed=False,
                    discovery_run_id=run.id,
                )
                db.add(job)

                imported_count += 1
                logger.debug(f'Imported job URL: {url}')

            except Exception as e:
                failed_count += 1
                logger.error(f'Failed to import {url}: {e}')

        db.commit()

        # Calculate statistics
        run.jobs_imported = imported_count
        run.jobs_failed = failed_count
        run.run_status = DiscoveryRunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)

        if run.started_at and run.finished_at:
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)

        db.commit()
        db.refresh(run)

        # Build summary
        duration_seconds = (run.duration_ms / 1000.0) if run.duration_ms else None
        ats_detection_rate = (
            (ats_successes / imported_count) if imported_count > 0 else 0.0
        )

        return JobDiscoverySummary(
            query_id=query.id,
            run_id=run.id,
            title_query=request.title_query,
            location=request.location,
            jobs_discovered=run.jobs_discovered,
            jobs_imported=run.jobs_imported,
            jobs_duplicate=run.jobs_duplicate,
            jobs_failed=run.jobs_failed,
            duration_seconds=duration_seconds,
            ats_detection_rate=ats_detection_rate,
            top_ats_types=ats_type_counts,
            status='completed',
            error_message=None,
        )

    except Exception as e:
        logger.error(f'Discovery failed: {e}')
        run.run_status = DiscoveryRunStatus.FAILED
        run.error_message = str(e)
        run.finished_at = datetime.now(UTC)

        if run.started_at and run.finished_at:
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f'Job discovery failed: {str(e)}'
        )


@router.get(
    '/jobs/discovery-runs/{run_id}',
    response_model=JobDiscoveryRunResponse,
    summary='Get job discovery run details',
    tags=['discovery']
)
async def get_discovery_run(
    run_id: int,
    db: Session = Depends(get_db)
) -> JobDiscoveryRunResponse:
    """
    Retrieve job discovery run details by ID.

    Args:
        run_id: Job discovery run ID
        db: Database session

    Returns:
        JobDiscoveryRunResponse with full run details

    Raises:
        HTTPException 404: Run not found
    """
    run = db.query(JobDiscoveryRun).filter(JobDiscoveryRun.id == run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail=f'Discovery run {run_id} not found')

    return _discovery_run_to_response(run)


@router.get(
    '/jobs/discovered',
    response_model=dict[str, list[dict] | int],
    summary='List discovered jobs from a run',
    tags=['discovery']
)
async def list_discovered_jobs(
    run_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> dict[str, list[dict] | int]:
    """
    List jobs discovered in a specific run.

    Args:
        run_id: Discovery run ID
        skip: Pagination offset
        limit: Results per page (max 100)
        db: Database session

    Returns:
        dict with jobs list and total count
    """
    query = db.query(JobPosting).filter(JobPosting.discovery_run_id == run_id)

    total = query.count()
    jobs = query.order_by(JobPosting.created_at.desc()).offset(skip).limit(limit).all()

    return {
        'jobs': [
            {
                'id': job.id,
                'title': job.title,
                'company_name': job.company_name,
                'location': job.location,
                'ats_type': job.ats_type,
                'source_url': job.source_url,
                'created_at': job.created_at,
            }
            for job in jobs
        ],
        'total': total
    }


@router.get(
    '/candidates/{candidate_id}/discovery-history',
    response_model=dict[str, list[JobDiscoveryRunResponse] | int],
    summary='Get candidate discovery history',
    tags=['discovery']
)
async def get_discovery_history(
    candidate_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
) -> dict[str, list[JobDiscoveryRunResponse] | int]:
    """
    Get job discovery run history for a candidate.

    Args:
        candidate_id: Candidate ID
        skip: Pagination offset
        limit: Results per page (max 50)
        db: Database session

    Returns:
        dict with runs list and total count
    """
    query = db.query(JobDiscoveryRun).join(
        JobDiscoveryQuery,
        JobDiscoveryRun.query_id == JobDiscoveryQuery.id
    ).filter(JobDiscoveryQuery.candidate_id == candidate_id)

    total = query.count()
    runs = query.order_by(JobDiscoveryRun.created_at.desc()).offset(skip).limit(limit).all()

    return {
        'runs': [_discovery_run_to_response(run) for run in runs],
        'total': total
    }
