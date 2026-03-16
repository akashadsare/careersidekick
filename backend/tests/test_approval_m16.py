"""M1.6: Approval Gate Tests

Test workflows:
- Retrieve draft for approval screen
- Edit answers and cover note
- Approve draft + snapshot creation
- Request revisions
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine, Base
from app.db_models import ApplicationDraft, CandidateProfile, DraftStatus, JobPosting
from app.services.approval_service import ApprovalService


@pytest.fixture(scope='function')
def db():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_candidate(db: Session) -> CandidateProfile:
    """Create sample candidate."""
    candidate = CandidateProfile(
        full_name='Alice Chen',
        email='alice@example.com',
        location='San Francisco, CA',
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@pytest.fixture
def sample_job(db: Session) -> JobPosting:
    """Create sample job."""
    job = JobPosting(
        title='Senior Backend Engineer',
        company_name='TechCorp',
        location='Remote',
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def sample_draft(db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting) -> ApplicationDraft:
    """Create sample draft."""
    draft = ApplicationDraft(
        candidate_id=sample_candidate.id,
        job_id=sample_job.id,
        fit_score=82,
        answers_json={
            'answers': [
                {
                    'question': 'Are you authorized to work?',
                    'answer': 'Yes, I am a US citizen.',
                    'provenance': 'candidate_answer',
                    'question_id': 1,
                },
                {
                    'question': 'Experience with Python?',
                    'answer': '5+ years',
                    'provenance': 'resume',
                    'question_id': 2,
                },
            ],
            'needs_review_flags': [],
        },
        cover_note='I am excited about this opportunity.',
        status=DraftStatus.DRAFT,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


class TestApprovalRetrieval:
    """Test retrieving drafts for approval screen."""

    def test_get_draft_for_approval(self, db: Session, sample_draft: ApplicationDraft):
        """Test retrieving draft details."""
        service = ApprovalService()
        result = service.get_draft_for_approval(sample_draft.id, db)

        assert result['draft_id'] == sample_draft.id
        assert result['candidate_name'] == 'Alice Chen'
        assert result['job_title'] == 'Senior Backend Engineer'
        assert result['company_name'] == 'TechCorp'
        assert result['fit_score'] == 82
        assert len(result['answers']) == 2

    def test_get_draft_not_found(self, db: Session):
        """Test retrieval fails for missing draft."""
        service = ApprovalService()
        with pytest.raises(ValueError, match='Draft .* not found'):
            service.get_draft_for_approval(99999, db)

    def test_get_draft_not_in_draft_status(self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting):
        """Test retrieval fails if draft already approved."""
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            fit_score=80,
            answers_json={'answers': []},
            cover_note='test',
            status=DraftStatus.APPROVED,
        )
        db.add(draft)
        db.commit()

        service = ApprovalService()
        with pytest.raises(ValueError, match='not in draft status'):
            service.get_draft_for_approval(draft.id, db)


class TestAnswerEditing:
    """Test editing answers and cover note."""

    def test_update_draft_answers(self, db: Session, sample_draft: ApplicationDraft):
        """Test updating answers in draft."""
        service = ApprovalService()

        updated_answers = [
            {
                'question': 'Are you authorized to work?',
                'answer': 'Yes, I am authorized without sponsorship.',  # Improved answer
                'provenance': 'candidate_answer',
                'question_id': 1,
            },
            {
                'question': 'Experience with Python?',
                'answer': '5+ years in production systems.',  # Enhanced detail
                'provenance': 'resume',
                'question_id': 2,
            },
        ]

        result = service.update_draft_answers(
            sample_draft.id,
            updated_answers,
            'I am very excited about this opportunity.',  # Improved cover note
            db,
        )

        assert result['answers'][0]['answer'] == 'Yes, I am authorized without sponsorship.'
        assert result['cover_note'] == 'I am very excited about this opportunity.'
        assert result['status'] == 'draft'

    def test_update_draft_cover_note_only(self, db: Session, sample_draft: ApplicationDraft):
        """Test updating just the cover note."""
        service = ApprovalService()

        result = service.update_draft_answers(
            sample_draft.id,
            sample_draft.answers_json['answers'],
            'Completely rewritten cover note.',
            db,
        )

        assert result['cover_note'] == 'Completely rewritten cover note.'

    def test_update_fails_if_not_draft_status(self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting):
        """Test update fails if draft not in draft status."""
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            fit_score=80,
            answers_json={'answers': []},
            cover_note='test',
            status=DraftStatus.APPROVED,
        )
        db.add(draft)
        db.commit()

        service = ApprovalService()
        with pytest.raises(ValueError, match='not in draft status'):
            service.update_draft_answers(draft.id, [], 'new note', db)


class TestApprovalWorkflow:
    """Test approval workflow."""

    def test_approve_draft(self, db: Session, sample_draft: ApplicationDraft):
        """Test approving draft."""
        service = ApprovalService()
        result = service.approve_draft(sample_draft.id, db)

        assert result['draft_id'] == sample_draft.id
        assert result['status'] == 'approved'
        assert result['approved_at'] is not None

        # Verify draft status changed in database
        draft_after = db.query(ApplicationDraft).filter(ApplicationDraft.id == sample_draft.id).first()
        assert draft_after.status == DraftStatus.APPROVED

    def test_approve_creates_timestamp(self, db: Session, sample_draft: ApplicationDraft):
        """Test approval includes timestamp."""
        service = ApprovalService()
        before = datetime.now(UTC)
        result = service.approve_draft(sample_draft.id, db)
        after = datetime.now(UTC)

        approved_time = datetime.fromisoformat(result['approved_at'])
        assert before <= approved_time <= after

    def test_approve_fails_if_not_draft(self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting):
        """Test approval fails if draft already approved."""
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            fit_score=80,
            answers_json={'answers': []},
            cover_note='test',
            status=DraftStatus.APPROVED,
        )
        db.add(draft)
        db.commit()

        service = ApprovalService()
        with pytest.raises(ValueError, match='not in draft status'):
            service.approve_draft(draft.id, db)


class TestRejectionWorkflow:
    """Test rejection/revision request workflow."""

    def test_reject_draft(self, db: Session, sample_draft: ApplicationDraft):
        """Test rejecting draft (requesting revisions)."""
        service = ApprovalService()
        result = service.reject_draft(
            sample_draft.id,
            'Please provide more detail on your experience with system design.',
            db,
        )

        # Draft stays in draft status
        assert result['status'] == 'draft'

        # Rejection reason logged
        assert 'approval_notes' in result['answers_json'] or 'approval_notes' in sample_draft.answers_json

    def test_draft_stays_editable_after_rejection(self, db: Session, sample_draft: ApplicationDraft):
        """Test draft remains editable after rejection."""
        service = ApprovalService()

        # Reject draft
        service.reject_draft(sample_draft.id, 'Need improvements', db)

        # Should still be able to update
        result = service.update_draft_answers(
            sample_draft.id,
            sample_draft.answers_json['answers'],
            'Improved cover note after feedback.',
            db,
        )

        assert result['cover_note'] == 'Improved cover note after feedback.'
        assert result['status'] == 'draft'


class TestConcurrentEditing:
    """Test concurrent editing support."""

    def test_get_draft_multiple_times(self, db: Session, sample_draft: ApplicationDraft):
        """Test getting draft multiple times (simulating concurrent users)."""
        service = ApprovalService()

        result1 = service.get_draft_for_approval(sample_draft.id, db)
        result2 = service.get_draft_for_approval(sample_draft.id, db)

        # Both retrievals should succeed and match
        assert result1['draft_id'] == result2['draft_id']
        assert result1['cover_note'] == result2['cover_note']

    def test_last_update_wins(self, db: Session, sample_draft: ApplicationDraft):
        """Test last update wins in concurrent editing scenario."""
        service = ApprovalService()

        # User 1 updates
        updated1 = service.update_draft_answers(
            sample_draft.id,
            sample_draft.answers_json['answers'],
            'User 1 version',
            db,
        )
        assert updated1['cover_note'] == 'User 1 version'

        # User 2 updates (overwrites)
        updated2 = service.update_draft_answers(
            sample_draft.id,
            sample_draft.answers_json['answers'],
            'User 2 version',
            db,
        )

        # User 2's version is final (last write wins)
        result = service.get_draft_for_approval(sample_draft.id, db)
        assert result['cover_note'] == 'User 2 version'


class TestApprovalStateTransitions:
    """Test valid state transitions."""

    def test_draft_to_approved(self, db: Session, sample_draft: ApplicationDraft):
        """Test valid transition: draft → approved."""
        assert sample_draft.status == DraftStatus.DRAFT

        service = ApprovalService()
        service.approve_draft(sample_draft.id, db)

        draft_after = db.query(ApplicationDraft).filter(ApplicationDraft.id == sample_draft.id).first()
        assert draft_after.status == DraftStatus.APPROVED

    def test_rejected_stays_draft(self, db: Session, sample_draft: ApplicationDraft):
        """Test rejection keeps draft in draft state."""
        service = ApprovalService()
        service.reject_draft(sample_draft.id, 'Need edits', db)

        draft_after = db.query(ApplicationDraft).filter(ApplicationDraft.id == sample_draft.id).first()
        assert draft_after.status == DraftStatus.DRAFT

    def test_approved_cannot_edit(self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting):
        """Test approved draft cannot be edited."""
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            fit_score=80,
            answers_json={'answers': []},
            cover_note='test',
            status=DraftStatus.APPROVED,
        )
        db.add(draft)
        db.commit()

        service = ApprovalService()
        with pytest.raises(ValueError, match='not in draft status'):
            service.update_draft_answers(draft.id, [], 'new notes', db)
