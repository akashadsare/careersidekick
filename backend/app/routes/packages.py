from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import ApplicationDraft, CandidateProfile, JobPosting
from ..models import (
    AnswerWithProvenance,
    NeedsReviewFlag,
    PackageGenerateRequest,
    PackageGenerateResponse,
    PackagePreviewRequest,
    PackagePreviewResponse,
)
from ..services.package_generator import generate_application_package

router = APIRouter()


@router.post('/preview', response_model=PackagePreviewResponse)
def package_preview(req: PackagePreviewRequest, db: Session = Depends(get_db)) -> PackagePreviewResponse:
    candidate = CandidateProfile(
        full_name=req.candidate_name,
        email=req.candidate_email,
        location=req.candidate_location,
    )
    db.add(candidate)

    job = JobPosting(
        title=req.role_title,
        company_name=req.company_name,
        ats_type='unknown',
    )
    db.add(job)
    db.flush()

    answers = [
        {
            'question': 'Are you authorized to work in this country?',
            'answer': 'Yes, I am authorized to work in the United States without sponsorship.',
            'provenance': 'answer_library',
        },
        {
            'question': 'Years of experience with Python?',
            'answer': '4+ years in production software and automation systems.',
            'provenance': 'resume_field',
        },
        {
            'question': 'Preferred work model?',
            'answer': 'Hybrid or remote, with occasional onsite collaboration as needed.',
            'provenance': 'profile_preference',
        },
    ]

    cover_note = (
        f'I am excited to apply for the {req.role_title} role at {req.company_name}. '
        'My recent experience building workflow automation and API-driven systems aligns well with this role. '
        'I would value the opportunity to contribute quickly and grow with your team.'
    )

    draft = ApplicationDraft(
        candidate_id=candidate.id,
        job_id=job.id,
        fit_score=83,
        answers_json={'answers': answers},
        cover_note=cover_note,
        status='draft',
    )
    db.add(draft)
    db.commit()

    return PackagePreviewResponse(
        draft_id=draft.id,
        candidate_name=req.candidate_name,
        role_title=req.role_title,
        company_name=req.company_name,
        fit_score=83,
        answers=answers,
        cover_note=cover_note,
    )


@router.post('/generate', response_model=PackageGenerateResponse)
def generate_package(req: PackageGenerateRequest, db: Session = Depends(get_db)) -> PackageGenerateResponse:
    """
    Generate customized application package for (candidate_id, job_id).

    Accepts:
    - candidate_id: Candidate profile ID (must exist)
    - job_id: Job posting ID (must exist)

    Returns:
    - Application package with generated answers, cover note, and needs_review flags
    - SLO: Complete within 30 seconds

    Raises:
    - 404: Candidate or job not found
    - 422: Package generation failed (e.g., no answer library questions available)
    """
    try:
        result = generate_application_package(req.candidate_id, req.job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=f'Package generation failed: {str(e)}') from e

    # Transform result into response
    answers = [
        AnswerWithProvenance(
            question=a['question'],
            answer=a['answer'],
            provenance=a['provenance'],
            question_id=a.get('question_id'),
        )
        for a in result['answers']
    ]

    needs_review = [
        NeedsReviewFlag(
            question=f['question'],
            reason=f['reason'],
            question_id=f.get('question_id'),
        )
        for f in result['needs_review_flags']
    ]

    return PackageGenerateResponse(
        package_id=result['package_id'],
        candidate_id=result['candidate_id'],
        job_id=result['job_id'],
        fit_score=result['fit_score'],
        answers=answers,
        cover_note=result['cover_note'],
        needs_review_flags=needs_review,
        created_at=datetime.now(UTC),
    )
