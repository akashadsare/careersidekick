"""M1.6: Approval Gate API endpoints

Endpoints:
- GET /api/v1/approvals/{draft_id} — Retrieve draft for approval screen
- PATCH /api/v1/approvals/{draft_id} — Update answers/cover note (user edits)
- POST /api/v1/approvals/{draft_id}/approve — Approve draft + create snapshot
- POST /api/v1/approvals/{draft_id}/reject — Request revisions
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import ApplicationDraft
from ..models import (
    AnswerForApproval,
    ApprovalScreenResponse,
    ApproveRequest,
    ApproveResponse,
    NeedsReviewFlag,
    RejectRequest,
    UpdateDraftRequest,
    UpdateDraftResponse,
)
from ..services.approval_service import ApprovalService

router = APIRouter()
approval_service = ApprovalService()


@router.get('/approvals/{draft_id}', response_model=ApprovalScreenResponse)
def get_approval_screen(draft_id: int, db: Session = Depends(get_db)) -> ApprovalScreenResponse:
    """
    Retrieve draft package for approval screen.

    Returns full package with:
    - Candidate + job details
    - All answers (editable)
    - Needs review flags
    - Cover note (editable)

    Args:
        draft_id: ApplicationDraft.id

    Returns:
        Full approval screen details

    Raises:
        404: Draft not found or not in draft status
    """
    try:
        draft_data = approval_service.get_draft_for_approval(draft_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Transform to response model
    answers = [
        AnswerForApproval(
            question=a['question'],
            answer=a['answer'],
            provenance=a['provenance'],
            question_id=a.get('question_id'),
        )
        for a in draft_data['answers']
    ]

    needs_review = [
        NeedsReviewFlag(
            question=f['question'],
            reason=f['reason'],
            question_id=f.get('question_id'),
        )
        for f in draft_data['needs_review_flags']
    ]

    return ApprovalScreenResponse(
        draft_id=draft_data['draft_id'],
        candidate_id=draft_data['candidate_id'],
        candidate_name=draft_data['candidate_name'],
        job_id=draft_data['job_id'],
        job_title=draft_data['job_title'],
        company_name=draft_data['company_name'],
        fit_score=draft_data['fit_score'],
        cover_note=draft_data['cover_note'],
        answers=answers,
        needs_review_flags=needs_review,
        status=draft_data['status'],
        created_at=draft_data['created_at'],
    )


@router.patch('/approvals/{draft_id}', response_model=UpdateDraftResponse)
def update_approval_draft(
    draft_id: int, payload: UpdateDraftRequest, db: Session = Depends(get_db)
) -> UpdateDraftResponse:
    """
    Update draft answers and cover note (user edits on approval screen).

    Allows user to:
    - Edit any answer
    - Rewrite cover note
    - Save changes back to draft

    Args:
        draft_id: ApplicationDraft.id
        payload: Updated answers + cover note

    Returns:
        Updated draft details

    Raises:
        404: Draft not found or not in draft status
        422: Invalid update (beyond recoverable changes)
    """
    try:
        # Convert AnswerForApproval back to dict for storage
        answers_list = [
            {
                'question': a.question,
                'answer': a.updated_answer if hasattr(a, 'updated_answer') else a.answer,
                'provenance': a.provenance,
                'question_id': a.question_id,
            }
            for a in payload.answers
        ]

        updated = approval_service.update_draft_answers(draft_id, answers_list, payload.cover_note, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=f'Update failed: {str(e)}') from e

    return UpdateDraftResponse(
        draft_id=updated['draft_id'],
        candidate_id=updated['candidate_id'],
        job_id=updated['job_id'],
        answers_count=len(updated['answers']),
        status=updated['status'],
        updated_at=datetime.now(UTC),
    )


@router.post('/approvals/{draft_id}/approve', response_model=ApproveResponse)
def approve_draft(
    draft_id: int, db: Session = Depends(get_db), s3_bucket: str | None = None
) -> ApproveResponse:
    """
    Approve draft package and create immutable snapshot.

    Marks ApplicationDraft as 'approved' and stores:
    - Snapshot in S3 (immutable audit trail)
    - Timestamp in database
    - Approval metadata

    Args:
        draft_id: ApplicationDraft.id
        s3_bucket: Optional S3 bucket for snapshot storage

    Returns:
        Approval confirmation with snapshot S3 key

    Raises:
        404: Draft not found or not in draft status (already approved/submitted)
        422: Snapshot creation failed
    """
    try:
        result = approval_service.approve_draft(draft_id, db, s3_bucket)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=f'Approval failed: {str(e)}') from e

    # Retrieve updated draft for response
    draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()

    return ApproveResponse(
        draft_id=result['draft_id'],
        status=result['status'],
        approved_at=datetime.fromisoformat(result['approved_at']),
        snapshot_s3_key=result['snapshot_s3_key'],
    )


@router.post('/approvals/{draft_id}/reject', response_model=ApprovalScreenResponse)
def reject_draft(
    draft_id: int, payload: RejectRequest, db: Session = Depends(get_db)
) -> ApprovalScreenResponse:
    """
    Request revisions for draft (rejection).

    Keeps draft in 'draft' status so user can continue editing.
    Logs rejection reason in draft for audit trail.

    Args:
        draft_id: ApplicationDraft.id
        payload: Rejection reason

    Returns:
        Updated draft details (ready for re-editing)

    Raises:
        404: Draft not found
        422: Rejection failed
    """
    try:
        updated = approval_service.reject_draft(draft_id, payload.reason, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=f'Rejection failed: {str(e)}') from e

    # Transform to response model
    answers = [
        AnswerForApproval(
            question=a['question'],
            answer=a['answer'],
            provenance=a['provenance'],
            question_id=a.get('question_id'),
        )
        for a in updated['answers']
    ]

    needs_review = [
        NeedsReviewFlag(
            question=f['question'],
            reason=f['reason'],
            question_id=f.get('question_id'),
        )
        for f in updated['needs_review_flags']
    ]

    return ApprovalScreenResponse(
        draft_id=updated['draft_id'],
        candidate_id=updated['candidate_id'],
        candidate_name=updated['candidate_name'],
        job_id=updated['job_id'],
        job_title=updated['job_title'],
        company_name=updated['company_name'],
        fit_score=updated['fit_score'],
        cover_note=updated['cover_note'],
        answers=answers,
        needs_review_flags=needs_review,
        status=updated['status'],
        created_at=updated['created_at'],
    )
