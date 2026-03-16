from datetime import datetime, UTC
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import JobPosting
from ..models import (
    JobCreateRequest,
    JobResponse,
    JobImportRequest,
    JobImportResponse,
    JobPostingResponse,
)
from ..services.job_extractor import JobExtractor

logger = logging.getLogger(__name__)

router = APIRouter()


def _job_to_response(job: JobPosting) -> JobPostingResponse:
    """Convert JobPosting ORM model to extended response schema."""
    return JobPostingResponse(
        id=job.id,
        title=job.title,
        company_name=job.company_name,
        location=job.location,
        description=job.description,
        apply_url=job.apply_url,
        source_url=job.source_url,
        ats_type=job.ats_type,
        ats_detection_confidence=job.ats_detection_confidence,
        is_closed=job.is_closed,
        extracted_at=job.extracted_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    '/import-by-url',
    response_model=JobImportResponse,
    summary='Import job posting from URL with ATS detection',
)
async def import_job_by_url(
    request: JobImportRequest,
    db: Session = Depends(get_db)
) -> JobImportResponse:
    """
    Import a job posting from a URL (M1.2).

    - Visits the provided URL
    - Extracts: title, company, location, description, ATS type
    - Detects if job is closed
    - Stores in database with extracted metadata
    - Returns detected ATS type with confidence score

    Accepts URLs from major ATS platforms:
    - Greenhouse (boards.greenhouse.io)
    - Lever (lever.co, jobs.lever.co)
    - Workday (myworkdayjobs.com)
    - Ashby (jobs.ashby.ai)
    - LinkedIn Jobs (linkedin.com/jobs)

    Args:
        request: JobImportRequest with source_url
        db: Database session

    Returns:
        JobImportResponse with extracted job, ATS type, and any warnings

    Raises:
        HTTPException 400: Invalid URL format
        HTTPException 422: Extraction failed (no title/company extracted)
        HTTPException 409: Job already exists (same URL)
    """
    source_url = request.source_url.strip()

    # Validate URL format
    if not source_url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=400,
            detail='URL must start with http:// or https://'
        )

    # Check if this URL was already imported
    existing_job = db.query(JobPosting).filter(
        JobPosting.source_url == source_url
    ).first()

    if existing_job:
        logger.info(f'Job already imported from URL: {source_url}')
        return JobImportResponse(
            job=_job_to_response(existing_job),
            is_closed=existing_job.is_closed,
            ats_type=existing_job.ats_type,
            ats_detection_confidence=existing_job.ats_detection_confidence,
            extraction_errors=['Job already imported from this URL']
        )

    # Extract job data from URL
    logger.info(f'Extracting job data from: {source_url}')
    extractor = JobExtractor(timeout=15)
    extracted_data = extractor.extract(source_url)

    # Validate minimum required fields
    if not extracted_data.get('title') or not extracted_data.get('company_name'):
        logger.error(
            f'Extraction failed for {source_url}: '
            f'title={extracted_data.get("title")}, '
            f'company={extracted_data.get("company_name")}'
        )
        raise HTTPException(
            status_code=422,
            detail=(
                'Could not extract job title and company from URL. '
                'Ensure the URL points to a valid job posting page.'
            )
        )

    # Create JobPosting record
    job = JobPosting(
        title=extracted_data['title'],
        company_name=extracted_data['company_name'],
        location=extracted_data.get('location'),
        description=extracted_data.get('description'),
        apply_url=extracted_data.get('apply_url') or source_url,
        source_url=source_url,
        ats_type=extracted_data.get('ats_type'),
        ats_detection_confidence=extracted_data.get('ats_detection_confidence'),
        is_closed=extracted_data.get('is_closed', False),
        extracted_at=datetime.now(UTC),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(
        f'Job imported successfully: {job.title} at {job.company_name} '
        f'(ID: {job.id}, ATS: {job.ats_type}, closed: {job.is_closed})'
    )

    extraction_errors = extracted_data.get('extraction_errors', [])
    if job.is_closed:
        extraction_errors.append('WARNING: Job posting is marked as closed')

    if not job.ats_type:
        extraction_errors.append(
            'Could not detect ATS type; manual verification may be needed'
        )
    elif job.ats_detection_confidence and job.ats_detection_confidence < 0.8:
        extraction_errors.append(
            f'ATS detection confidence low ({job.ats_detection_confidence:.0%}); '
            'verify ATS type is correct'
        )

    return JobImportResponse(
        job=_job_to_response(job),
        is_closed=job.is_closed,
        ats_type=job.ats_type,
        ats_detection_confidence=job.ats_detection_confidence,
        extraction_errors=extraction_errors
    )


@router.post('', response_model=JobResponse)
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)) -> JobResponse:
    job = JobPosting(
        title=payload.title,
        company_name=payload.company_name,
        apply_url=payload.apply_url,
        ats_type=payload.ats_type or 'unknown',
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse(
        id=job.id,
        title=job.title,
        company_name=job.company_name,
        apply_url=job.apply_url,
        ats_type=job.ats_type,
    )


@router.get('', response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[JobResponse]:
    rows = db.query(JobPosting).order_by(JobPosting.id.desc()).limit(100).all()
    return [
        JobResponse(
            id=row.id,
            title=row.title,
            company_name=row.company_name,
            apply_url=row.apply_url,
            ats_type=row.ats_type,
        )
        for row in rows
    ]


@router.get('/{job_id}', response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    row = db.get(JobPosting, job_id)
    if not row:
        raise HTTPException(status_code=404, detail='job not found')

    return JobResponse(
        id=row.id,
        title=row.title,
        company_name=row.company_name,
        apply_url=row.apply_url,
        ats_type=row.ats_type,
    )
