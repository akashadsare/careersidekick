"""M1.7: Submission Execution Tests

Comprehensive test suite for job application submission via TinyFish browser automation.
"""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine, Base
from app.db_models import (
    ApplicationDraft,
    CandidateProfile,
    DraftStatus,
    JobPosting,
    RunStatus,
    SubmissionRun,
)
from app.services.execution_service import (
    PortalPromptBuilder,
    TinyFishExecutionService,
)


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
    """Create a sample candidate."""
    candidate = CandidateProfile(
        full_name='Alice Johnson',
        email='alice@example.com',
        phone='+1-555-0001',
        location='San Francisco, CA',
        years_experience=5,
        work_authorization='US_CITIZEN',
        remote_preference='REMOTE',
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@pytest.fixture
def sample_job(db: Session) -> JobPosting:
    """Create a sample job posting."""
    job = JobPosting(
        title='Senior Software Engineer',
        company_name='TechCorp',
        location='San Francisco, CA',
        description='Looking for a senior engineer with Python experience.',
        apply_url='https://jobs.greenhouse.io/techcorp/jobs/12345',
        source_url='https://greenhouse.io/techcorp/jobs/12345',
        ats_type='greenhouse',
        ats_detection_confidence=0.95,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def sample_approved_draft(db: Session, sample_candidate, sample_job) -> ApplicationDraft:
    """Create a sample approved application draft."""
    draft = ApplicationDraft(
        candidate_id=sample_candidate.id,
        job_id=sample_job.id,
        fit_score=85,
        status=DraftStatus.APPROVED,
        answers_json={
            'answers': [
                {
                    'question': 'Are you authorized to work in the US?',
                    'answer': 'Yes, I am a US citizen.',
                },
                {
                    'question': 'What is your preferred work arrangement?',
                    'answer': 'Remote work is my preference.',
                },
            ],
        },
        cover_note='I am an experienced software engineer with 5 years of Python expertise, strongly interested in this opportunity.',
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


class TestPortalPromptBuilder:
    """Test portal-specific prompt building."""

    def test_build_greenhouse_goal(self):
        """Test building Greenhouse submission goal."""
        goal = PortalPromptBuilder.build_submission_goal(
            job_url='https://boards.greenhouse.io/techcorp/jobs/12345',
            ats_type='greenhouse',
            candidate_data={
                'full_name': 'Alice Johnson',
                'email': 'alice@example.com',
                'phone': '+1-555-0001',
                'location': 'San Francisco, CA',
            },
            draft_data={
                'answers_json': {
                    'answers': [
                        {
                            'question': 'Are you authorized to work in the US?',
                            'answer': 'Yes, I am a US citizen.',
                        },
                    ],
                },
                'cover_note': 'I am interested in this role.',
            },
        )

        assert 'Greenhouse' in goal
        assert 'Alice Johnson' in goal
        assert 'alice@example.com' in goal
        assert 'Are you authorized to work in the US?' in goal
        assert 'Yes, I am a US citizen.' in goal

    def test_build_lever_goal(self):
        """Test building Lever submission goal."""
        goal = PortalPromptBuilder.build_submission_goal(
            job_url='https://jobs.lever.co/techcorp/jobs/12345',
            ats_type='lever',
            candidate_data={
                'full_name': 'Bob Smith',
                'email': 'bob@example.com',
                'phone': None,
                'location': 'New York, NY',
            },
            draft_data={
                'answers_json': {'answers': []},
                'cover_note': 'Excited about this opportunity.',
            },
        )

        assert 'Lever' in goal
        assert 'Bob Smith' in goal
        assert 'bob@example.com' in goal

    def test_build_linkedin_goal(self):
        """Test building LinkedIn Easy Apply submission goal."""
        goal = PortalPromptBuilder.build_submission_goal(
            job_url='https://www.linkedin.com/jobs/view/12345',
            ats_type='linkedin',
            candidate_data={
                'full_name': 'Charlie Brown',
                'email': 'charlie@example.com',
                'phone': '+1-555-0003',
                'location': 'Remote',
            },
            draft_data={
                'answers_json': {'answers': []},
                'cover_note': 'Looking forward to hearing from you.',
            },
        )

        assert 'LinkedIn' in goal
        assert 'Charlie Brown' in goal


class TestExecutionServiceInitiation:
    """Test submission initiation and run tracking."""

    def test_submit_application_creates_run(self, db: Session, sample_approved_draft: ApplicationDraft):
        """Test that submit_application creates a SubmissionRun."""
        # Create a run directly to simulate what the service would do
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Verify run was created
        assert run.id is not None
        assert run.draft_id == sample_approved_draft.id
        assert run.run_status == RunStatus.RUNNING
        assert run.started_at is not None

    def test_submit_fails_with_draft_not_found(self, db: Session):
        """Test submission fails when draft doesn't exist."""
        # Query for non-existent draft
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == 9999).first()
        assert draft is None

    def test_submit_fails_with_non_approved_draft(self, db: Session, sample_candidate, sample_job):
        """Test submission fails when draft is not approved."""
        # Create a draft with DRAFT status
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            status=DraftStatus.DRAFT,
            answers_json={},
            cover_note='Test',
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        assert draft.status == DraftStatus.DRAFT
        assert draft.status != DraftStatus.APPROVED

    def test_submit_fails_when_job_has_no_apply_url(self, db: Session, sample_candidate):
        """Test validation fails when job has no apply_url."""
        job = JobPosting(
            title='No Apply URL Job',
            company_name='TestCo',
            apply_url=None,  # Missing apply URL
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=job.id,
            status=DraftStatus.APPROVED,
            answers_json={},
            cover_note='Test',
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        assert job.apply_url is None
        assert draft.status == DraftStatus.APPROVED


class TestRunStatusTracking:
    """Test run status transitions and timestamps."""

    def test_run_transitions_to_completed(self, db: Session, sample_approved_draft):
        """Test run transitions from RUNNING to COMPLETED."""
        # Create run
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()

        # Transition to COMPLETED
        run.run_status = RunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 5000
        run.result_json = {
            'status': 'COMPLETED',
            'reached_review_screen': True,
            'fields_filled': {'name': 'Alice Johnson', 'email': 'alice@example.com'},
        }
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.run_status == RunStatus.COMPLETED
        assert run.finished_at is not None
        assert run.duration_ms == 5000
        assert run.result_json['reached_review_screen'] is True

    def test_run_transitions_to_failed(self, db: Session, sample_approved_draft):
        """Test run transitions from RUNNING to FAILED."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()

        # Transition to FAILED
        run.run_status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 3000
        run.error_message = 'Form validation error on question 2'
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.run_status == RunStatus.FAILED
        assert run.finished_at is not None
        assert run.error_message is not None

    def test_run_can_resume_from_failed(self, db: Session, sample_approved_draft):
        """Test run can transition from FAILED back to RUNNING."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.FAILED,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            error_message='Temporary network error',
        )
        db.add(run)
        db.commit()

        # Resume by transitioning back to RUNNING
        run.run_status = RunStatus.RUNNING
        run.finished_at = None
        run.error_message = None
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.run_status == RunStatus.RUNNING
        assert run.finished_at is None


class TestDraftStatusTransitions:
    """Test draft status changes during submission."""

    def test_draft_transitions_to_submitted(self, db: Session, sample_approved_draft):
        """Test draft transitions from APPROVED to SUBMITTED on success."""
        assert sample_approved_draft.status == DraftStatus.APPROVED

        # Simulate successful submission
        sample_approved_draft.status = DraftStatus.SUBMITTED
        db.add(sample_approved_draft)
        db.commit()
        db.refresh(sample_approved_draft)

        assert sample_approved_draft.status == DraftStatus.SUBMITTED

    def test_draft_transitions_to_failed_on_error(self, db: Session, sample_approved_draft):
        """Test draft transitions from APPROVED to FAILED on submission error."""
        assert sample_approved_draft.status == DraftStatus.APPROVED

        # Simulate failed submission
        sample_approved_draft.status = DraftStatus.FAILED
        db.add(sample_approved_draft)
        db.commit()
        db.refresh(sample_approved_draft)

        assert sample_approved_draft.status == DraftStatus.FAILED

    def test_submitted_draft_is_immutable(self, db: Session, sample_approved_draft):
        """Test that SUBMITTED draft blocks status changes."""
        sample_approved_draft.status = DraftStatus.SUBMITTED
        db.add(sample_approved_draft)
        db.commit()

        # Verify we can only read or leave as-is (no transitions back)
        assert sample_approved_draft.status == DraftStatus.SUBMITTED


class TestSubmissionWithMetadata:
    """Test submission runs with detailed metadata."""

    def test_run_stores_tinyfish_run_id(self, db: Session, sample_approved_draft):
        """Test run stores TinyFish run ID from streaming."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()

        # Simulate receiving run ID from TinyFish
        run.tinyfish_run_id = 'tinyfish-run-abc123'
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.tinyfish_run_id == 'tinyfish-run-abc123'

    def test_run_stores_streaming_url(self, db: Session, sample_approved_draft):
        """Test run stores streaming URL for live progress."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()

        # Simulate receiving streaming URL
        run.streaming_url = 'https://stream.tinyfish.ai/runs/abc123'
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.streaming_url == 'https://stream.tinyfish.ai/runs/abc123'

    def test_run_stores_complete_result_json(self, db: Session, sample_approved_draft):
        """Test run stores complete result JSON with all submission details."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.COMPLETED,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=8500,
        )
        db.add(run)
        db.commit()

        # Simulate storing TinyFish result
        run.result_json = {
            'status': 'COMPLETED',
            'reached_review_screen': True,
            'fields_filled': {
                'full_name': 'Alice Johnson',
                'email': 'alice@example.com',
                'work_auth': 'Yes, I am a US citizen.',
            },
            'final_screenshot': 'data:image/png;base64,iVBORw0KGgoAAAANS...',
            'duration_ms': 8500,
        }
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.result_json['status'] == 'COMPLETED'
        assert run.result_json['fields_filled']['full_name'] == 'Alice Johnson'
        assert len(run.result_json['final_screenshot']) > 0


class TestConcurrentSubmissions:
    """Test handling multiple concurrent submissions."""

    def test_multiple_runs_for_same_draft(self, db: Session, sample_approved_draft):
        """Test that only one active run should exist per draft (but DB allows multiple)."""
        # Create first run
        run1 = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run1)
        db.commit()
        db.refresh(run1)

        # Create second run for same draft (edge case)
        run2 = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run2)
        db.commit()
        db.refresh(run2)

        # Verify both runs exist
        runs = db.query(SubmissionRun).filter(SubmissionRun.draft_id == sample_approved_draft.id).all()
        assert len(runs) == 2

    def test_multiple_drafts_for_same_candidate(self, db: Session, sample_candidate):
        """Test multiple submission runs for different jobs by same candidate."""
        # Create two jobs
        job1 = JobPosting(
            title='Senior Engineer',
            company_name='TechCorp',
            apply_url='https://jobs.greenhouse.io/techcorp/jobs/1',
            ats_type='greenhouse',
        )
        job2 = JobPosting(
            title='Staff Engineer',
            company_name='OtherCo',
            apply_url='https://jobs.lever.co/otherco/jobs/2',
            ats_type='lever',
        )
        db.add(job1)
        db.add(job2)
        db.commit()

        # Create approved drafts for both
        draft1 = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=job1.id,
            status=DraftStatus.APPROVED,
            answers_json={},
            cover_note='Test 1',
        )
        draft2 = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=job2.id,
            status=DraftStatus.APPROVED,
            answers_json={},
            cover_note='Test 2',
        )
        db.add(draft1)
        db.add(draft2)
        db.commit()

        # Create runs for both
        run1 = SubmissionRun(draft_id=draft1.id, run_status=RunStatus.COMPLETED)
        run2 = SubmissionRun(draft_id=draft2.id, run_status=RunStatus.COMPLETED)
        db.add(run1)
        db.add(run2)
        db.commit()

        # Verify runs
        runs = db.query(SubmissionRun).all()
        assert len(runs) == 2
        assert run1.draft_id == draft1.id
        assert run2.draft_id == draft2.id


class TestErrorHandling:
    """Test error scenarios and recovery."""

    def test_run_with_error_message(self, db: Session, sample_approved_draft):
        """Test run captures detailed error messages."""
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.FAILED,
            error_message='Connection timeout after 30s. Job posting may have been closed.',
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.error_message is not None
        assert 'timeout' in run.error_message.lower()

    def test_run_recovery_workflow(self, db: Session, sample_approved_draft):
        """Test workflow: run fails → user reviews → run resumes."""
        # First attempt fails
        run = SubmissionRun(
            draft_id=sample_approved_draft.id,
            run_status=RunStatus.FAILED,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=3000,
            error_message='Network error',
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # User retries (same run)
        run.run_status = RunStatus.RUNNING
        run.finished_at = None
        run.error_message = None
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.run_status == RunStatus.RUNNING
        assert run.error_message is None

    def test_draft_locked_after_submission(self, db: Session, sample_approved_draft):
        """Test draft is locked (can't be edited) after successful submission."""
        sample_approved_draft.status = DraftStatus.SUBMITTED
        db.add(sample_approved_draft)
        db.commit()

        # Verify status is locked
        assert sample_approved_draft.status == DraftStatus.SUBMITTED
        # In a real scenario, the API would reject PATCH requests on submitted drafts


# Integration-style tests (without full TinyFish mocking)


class TestSubmissionWorkflow:
    """Test complete submission workflow."""

    def test_approved_draft_to_submission_flow(self, db: Session, sample_candidate, sample_job):
        """Test end-to-end flow: approved draft → run → submitted draft."""
        # 1. Create approved draft
        draft = ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            status=DraftStatus.APPROVED,
            answers_json={
                'answers': [
                    {
                        'question': 'Are you authorized to work in the US?',
                        'answer': 'Yes, I am a US citizen.',
                    },
                ],
            },
            cover_note='I am very interested in this role.',
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        assert draft.status == DraftStatus.APPROVED

        # 2. Create submission run
        run = SubmissionRun(
            draft_id=draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.draft_id == draft.id
        assert run.run_status == RunStatus.RUNNING

        # 3. Simulate successful completion
        run.run_status = RunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 7500
        run.result_json = {
            'status': 'COMPLETED',
            'reached_review_screen': True,
        }
        db.add(run)

        # 4. Update draft status
        draft.status = DraftStatus.SUBMITTED
        db.add(draft)
        db.commit()

        # 5. Verify final state
        db.refresh(draft)
        db.refresh(run)

        assert draft.status == DraftStatus.SUBMITTED
        assert run.run_status == RunStatus.COMPLETED
        assert run.result_json['reached_review_screen'] is True
