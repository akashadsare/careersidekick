from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import CandidateProfile
from ..models import CandidateCreateRequest, CandidateResponse

router = APIRouter()


@router.post('', response_model=CandidateResponse)
def create_candidate(payload: CandidateCreateRequest, db: Session = Depends(get_db)) -> CandidateResponse:
    candidate = CandidateProfile(
        full_name=payload.full_name,
        email=payload.email,
        location=payload.location,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return CandidateResponse(id=candidate.id, full_name=candidate.full_name, email=candidate.email, location=candidate.location)


@router.get('', response_model=list[CandidateResponse])
def list_candidates(db: Session = Depends(get_db)) -> list[CandidateResponse]:
    rows = db.query(CandidateProfile).order_by(CandidateProfile.id.desc()).limit(100).all()
    return [
        CandidateResponse(id=row.id, full_name=row.full_name, email=row.email, location=row.location)
        for row in rows
    ]


@router.get('/{candidate_id}', response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)) -> CandidateResponse:
    row = db.get(CandidateProfile, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail='candidate not found')

    return CandidateResponse(id=row.id, full_name=row.full_name, email=row.email, location=row.location)
