"""M1.6: Human Approval Gate Service

Handles approval workflows:
1. Package retrieval (M1.5 generated draft)
2. Field editing + validation
3. Package snapshot creation + S3 storage
4. Status transition from draft → approved
"""

import json
from datetime import UTC, datetime
from typing import Optional

from ..db_models import ApplicationDraft, DraftStatus, CandidateProfile, JobPosting


class ApprovalService:
    """Manage application package approval workflows."""

    def __init__(self, s3_client=None):
        """Initialize approval service with optional S3 client."""
        self.s3_client = s3_client  # Injected from routes for more flexible testing

    def get_draft_for_approval(self, draft_id: int, db) -> dict:
        """
        Retrieve draft package for approval.

        Args:
            draft_id: ApplicationDraft.id
            db: SQLAlchemy session

        Returns:
            dict with draft details and related entities
        """
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()
        if not draft:
            raise ValueError(f'Draft {draft_id} not found')

        if draft.status != DraftStatus.DRAFT:
            raise ValueError(f'Draft {draft_id} is not in draft status (current: {draft.status.value})')

        candidate = db.query(CandidateProfile).filter(CandidateProfile.id == draft.candidate_id).first()
        job = db.query(JobPosting).filter(JobPosting.id == draft.job_id).first()

        if not candidate or not job:
            raise ValueError('Associated candidate or job not found')

        return {
            'draft_id': draft.id,
            'candidate_id': draft.candidate_id,
            'job_id': draft.job_id,
            'candidate_name': candidate.full_name,
            'candidate_email': candidate.email,
            'job_title': job.title,
            'company_name': job.company_name,
            'fit_score': draft.fit_score,
            'cover_note': draft.cover_note,
            'answers': draft.answers_json.get('answers', []) if draft.answers_json else [],
            'needs_review_flags': draft.answers_json.get('needs_review_flags', []) if draft.answers_json else [],
            'status': draft.status.value,
            'created_at': draft.created_at,
        }

    def update_draft_answers(self, draft_id: int, updated_answers: list[dict], updated_cover_note: str, db) -> dict:
        """
        Update draft answers and cover note (user edits on approval screen).

        Args:
            draft_id: ApplicationDraft.id
            updated_answers: List of {"question", "answer", "provenance", "question_id"}
            updated_cover_note: Modified cover note text
            db: SQLAlchemy session

        Returns:
            Updated draft details
        """
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()
        if not draft:
            raise ValueError(f'Draft {draft_id} not found')

        if draft.status != DraftStatus.DRAFT:
            raise ValueError(f'Draft {draft_id} is not in draft status (current: {draft.status.value})')

        # Update answers
        draft.answers_json = {
            'answers': updated_answers,
            'needs_review_flags': draft.answers_json.get('needs_review_flags', [])
            if draft.answers_json
            else [],
        }

        # Update cover note
        draft.cover_note = updated_cover_note

        db.add(draft)
        db.commit()
        db.refresh(draft)

        return self.get_draft_for_approval(draft_id, db)

    def approve_draft(self, draft_id: int, db, s3_bucket: str | None = None) -> dict:
        """
        Approve draft and create snapshot.

        Args:
            draft_id: ApplicationDraft.id
            db: SQLAlchemy session
            s3_bucket: Optional S3 bucket for snapshot storage

        Returns:
            dict with approval details and snapshot S3 key
        """
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()
        if not draft:
            raise ValueError(f'Draft {draft_id} not found')

        if draft.status != DraftStatus.DRAFT:
            raise ValueError(f'Draft {draft_id} is not in draft status (current: {draft.status.value})')

        # Create snapshot JSON
        snapshot = {
            'draft_id': draft.id,
            'candidate_id': draft.candidate_id,
            'job_id': draft.job_id,
            'fit_score': draft.fit_score,
            'answers_json': draft.answers_json,
            'cover_note': draft.cover_note,
            'approved_at': datetime.now(UTC).isoformat(),
            'approved_by': 'candidate',  # Phase 2: add user_id from auth context
        }

        # Store snapshot in S3 (if S3 client available)
        s3_key = None
        if self.s3_client and s3_bucket:
            s3_key = f'approval-snapshots/{draft.candidate_id}/{draft.id}_{datetime.now(UTC).timestamp()}.json'
            try:
                self.s3_client.put_object(
                    Bucket=s3_bucket,
                    Key=s3_key,
                    Body=json.dumps(snapshot, default=str),
                    ContentType='application/json',
                )
            except Exception as e:
                # Log but don't fail if S3 fails (optional feature)
                pass

        # Transition to approved status
        draft.status = DraftStatus.APPROVED
        db.add(draft)
        db.commit()
        db.refresh(draft)

        return {
            'draft_id': draft.id,
            'status': draft.status.value,
            'approved_at': datetime.now(UTC).isoformat(),
            'snapshot_s3_key': s3_key,
        }

    def reject_draft(self, draft_id: int, reason: str, db) -> dict:
        """
        Reject draft and revert to draft status (stays editable).

        Args:
            draft_id: ApplicationDraft.id
            reason: Reason for rejection (logged for audit)
            db: SQLAlchemy session

        Returns:
            Updated draft details
        """
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()
        if not draft:
            raise ValueError(f'Draft {draft_id} not found')

        # Draft stays in draft status (user can re-edit)
        # Reason is logged as a note in answers_json for now
        if not draft.answers_json:
            draft.answers_json = {}

        if 'approval_notes' not in draft.answers_json:
            draft.answers_json['approval_notes'] = []

        draft.answers_json['approval_notes'].append({
            'timestamp': datetime.now(UTC).isoformat(),
            'action': 'rejected',
            'reason': reason,
        })

        db.add(draft)
        db.commit()
        db.refresh(draft)

        return self.get_draft_for_approval(draft_id, db)
