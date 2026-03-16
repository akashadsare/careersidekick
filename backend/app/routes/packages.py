from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import ApplicationDraft, CandidateProfile, JobPosting
from ..models import PackagePreviewRequest, PackagePreviewResponse

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
