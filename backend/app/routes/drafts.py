from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import ApplicationDraft, DraftStatus, SubmissionRun
from ..models import DraftResponse, DraftUpdateRequest, DraftUpdateResponse, SubmissionRunResponse

router = APIRouter()


@router.get('', response_model=list[DraftResponse])
def list_drafts(db: Session = Depends(get_db)) -> list[DraftResponse]:
    rows = db.query(ApplicationDraft).order_by(ApplicationDraft.id.desc()).limit(100).all()
    return [
        DraftResponse(
            id=row.id,
            candidate_id=row.candidate_id,
            job_id=row.job_id,
            fit_score=row.fit_score,
            answers_json=row.answers_json,
            cover_note=row.cover_note,
            status=row.status.value,
        )
        for row in rows
    ]


@router.get('/{draft_id}', response_model=DraftResponse)
def get_draft(draft_id: int, db: Session = Depends(get_db)) -> DraftResponse:
    row = db.get(ApplicationDraft, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail='draft not found')
    return DraftResponse(
        id=row.id,
        candidate_id=row.candidate_id,
        job_id=row.job_id,
        fit_score=row.fit_score,
        answers_json=row.answers_json,
        cover_note=row.cover_note,
        status=row.status.value,
    )


@router.patch('/{draft_id}', response_model=DraftUpdateResponse)
def update_draft(draft_id: int, payload: DraftUpdateRequest, db: Session = Depends(get_db)) -> DraftUpdateResponse:
    row = db.get(ApplicationDraft, draft_id)
    if not row:
        raise HTTPException(status_code=404, detail='draft not found')

    if payload.answers_json is not None:
        row.answers_json = payload.answers_json
    if payload.cover_note is not None:
        row.cover_note = payload.cover_note
    if payload.status is not None:
        row.status = DraftStatus(payload.status)

    db.add(row)
    db.commit()
    db.refresh(row)

    return DraftUpdateResponse(id=row.id, status=row.status.value, cover_note=row.cover_note, answers_json=row.answers_json)


@router.get('/{draft_id}/runs', response_model=list[SubmissionRunResponse])
def list_draft_runs(draft_id: int, db: Session = Depends(get_db)) -> list[SubmissionRunResponse]:
    draft = db.get(ApplicationDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail='draft not found')

    runs = db.query(SubmissionRun).filter(SubmissionRun.draft_id == draft_id).order_by(SubmissionRun.id.desc()).all()
    return [
        SubmissionRunResponse(
            id=run.id,
            draft_id=run.draft_id,
            tinyfish_run_id=run.tinyfish_run_id,
            run_status=run.run_status.value,
            streaming_url=run.streaming_url,
            error_message=run.error_message,
            created_at=run.created_at,
        )
        for run in runs
    ]
