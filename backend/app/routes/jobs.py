from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import JobPosting
from ..models import JobCreateRequest, JobResponse

router = APIRouter()


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
