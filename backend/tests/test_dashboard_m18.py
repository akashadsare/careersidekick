"""M1.8: Applications Dashboard Tests

Test suite for dashboard queries, analytics, and detail views.
"""

from datetime import UTC, datetime, timedelta

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
from app.services.dashboard_service import DashboardService


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
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@pytest.fixture
def sample_jobs(db: Session) -> list[JobPosting]:
    """Create multiple sample jobs."""
    jobs = [
        JobPosting(
            title='Senior Engineer',
            company_name='TechCorp',
            location='San Francisco, CA',
            apply_url='https://techcorp.jobs/1',
            ats_type='greenhouse',
        ),
        JobPosting(
            title='Backend Engineer',
            company_name='TechCorp',
            location='Remote',
            apply_url='https://techcorp.jobs/2',
            ats_type='greenhouse',
        ),
        JobPosting(
            title='Full Stack Engineer',
            company_name='StartupXYZ',
            location='New York, NY',
            apply_url='https://startupxyz.jobs/1',
            ats_type='lever',
        ),
        JobPosting(
            title='ML Engineer',
            company_name='DataCo',
            location='Remote',
            apply_url='https://dataco.jobs/1',
            ats_type='linkedin',
        ),
    ]
    for job in jobs:
        db.add(job)
    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


@pytest.fixture
def sample_drafts(db: Session, sample_candidate, sample_jobs):
    """Create drafts with various statuses."""
    now = datetime.now(UTC)
    drafts = [
        ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_jobs[0].id,
            fit_score=85,
            status=DraftStatus.DRAFT,
            answers_json={},
            cover_note='Interested',
            created_at=now,
        ),
        ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_jobs[1].id,
            fit_score=75,
            status=DraftStatus.APPROVED,
            answers_json={},
            cover_note='Looking forward',
            created_at=now - timedelta(days=1),
        ),
        ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_jobs[2].id,
            fit_score=90,
            status=DraftStatus.SUBMITTED,
            answers_json={},
            cover_note='Excited',
            created_at=now - timedelta(days=3),
        ),
        ApplicationDraft(
            candidate_id=sample_candidate.id,
            job_id=sample_jobs[3].id,
            fit_score=60,
            status=DraftStatus.FAILED,
            answers_json={},
            cover_note='Testing',
            created_at=now - timedelta(days=7),
        ),
    ]
    for draft in drafts:
        db.add(draft)
    db.commit()
    for draft in drafts:
        db.refresh(draft)
    return drafts


class TestSubmissionSummary:
    """Test submission summary statistics."""

    def test_get_summary_counts_by_status(self, db: Session, sample_candidate, sample_drafts):
        """Test summary counts submissions by status."""
        summary = DashboardService.get_submission_summary(sample_candidate.id, db, days=30)

        assert summary['total_drafts'] == 4
        assert summary['by_status']['draft'] == 1
        assert summary['by_status']['approved'] == 1
        assert summary['by_status']['submitted'] == 1
        assert summary['by_status']['failed'] == 1

    def test_get_summary_fit_scores(self, db: Session, sample_candidate, sample_drafts):
        """Test summary calculates fit score statistics."""
        summary = DashboardService.get_submission_summary(sample_candidate.id, db, days=30)

        assert summary['avg_fit_score'] == 77.5  # (85 + 75 + 90 + 60) / 4
        assert summary['max_fit_score'] == 90

    def test_get_summary_completion_rate(self, db: Session, sample_candidate, sample_drafts):
        """Test summary calculates submission completion rate."""
        summary = DashboardService.get_submission_summary(sample_candidate.id, db, days=30)

        # 1 submitted out of 4 = 25%
        assert summary['submission_completion_rate'] == 25.0

    def test_get_summary_time_window_filtering(self, db: Session, sample_candidate, sample_drafts):
        """Test summary respects time window."""
        # Only created in last 2 days should include draft, approved, submitted (not failed)
        summary = DashboardService.get_submission_summary(sample_candidate.id, db, days=2)

        assert summary['total_drafts'] == 3
        assert summary['by_status']['draft'] == 1
        assert summary['by_status']['failed'] == 0


class TestListSubmissions:
    """Test submission list with filtering."""

    def test_list_all_submissions(self, db: Session, sample_candidate, sample_drafts):
        """Test listing all submissions for a candidate."""
        submissions, total = DashboardService.list_submissions(sample_candidate.id, db)

        assert len(submissions) == 4
        assert total == 4

    def test_list_with_status_filter(self, db: Session, sample_candidate, sample_drafts):
        """Test filtering by status."""
        submissions, total = DashboardService.list_submissions(
            sample_candidate.id, db, status_filter='submitted'
        )

        assert len(submissions) == 1
        assert total == 1
        assert submissions[0]['draft_status'] == 'submitted'

    def test_list_with_company_filter(self, db: Session, sample_candidate, sample_drafts):
        """Test filtering by company name."""
        submissions, total = DashboardService.list_submissions(
            sample_candidate.id, db, company_filter='TechCorp'
        )

        assert len(submissions) == 2
        assert total == 2
        assert all(s['company_name'] == 'TechCorp' for s in submissions)

    def test_list_with_pagination(self, db: Session, sample_candidate, sample_drafts):
        """Test pagination."""
        page1, total = DashboardService.list_submissions(
            sample_candidate.id, db, limit=2, offset=0
        )
        page2, _ = DashboardService.list_submissions(
            sample_candidate.id, db, limit=2, offset=2
        )

        assert len(page1) == 2
        assert len(page2) == 2
        assert total == 4
        assert page1[0]['draft_id'] != page2[0]['draft_id']

    def test_list_includes_run_info(self, db: Session, sample_candidate, sample_drafts):
        """Test list includes submission run information."""
        # Create a run for the submitted draft
        submitted_draft = [d for d in sample_drafts if d.status == DraftStatus.SUBMITTED][0]
        run = SubmissionRun(
            draft_id=submitted_draft.id,
            run_status=RunStatus.COMPLETED,
            duration_ms=8500,
        )
        db.add(run)
        db.commit()

        submissions, _ = DashboardService.list_submissions(sample_candidate.id, db)

        submitted = [s for s in submissions if s['draft_id'] == submitted_draft.id][0]
        assert submitted['run_id'] is not None
        assert submitted['run_status'] == 'completed'
        assert submitted['run_duration_ms'] == 8500


class TestSubmissionDetail:
    """Test detailed submission view."""

    def test_get_detail_missing_draft(self, db: Session):
        """Test detail lookup fails for missing draft."""
        with pytest.raises(ValueError, match='not found'):
            DashboardService.get_submission_detail(9999, db)

    def test_get_detail_includes_answers(self, db: Session, sample_candidate, sample_drafts):
        """Test detail includes answers and cover note."""
        draft = sample_drafts[0]
        draft.answers_json = {
            'answers': [
                {'question': 'Work auth?', 'answer': 'Yes'},
                {'question': 'Remote?', 'answer': 'Preferred'},
            ]
        }
        draft.cover_note = 'I am interested in this role.'
        db.add(draft)
        db.commit()

        detail = DashboardService.get_submission_detail(draft.id, db)

        assert detail['draft_id'] == draft.id
        assert len(detail['answers']) == 2
        assert detail['cover_note'] == 'I am interested in this role.'

    def test_get_detail_includes_run_history(self, db: Session, sample_candidate, sample_drafts):
        """Test detail includes full run history."""
        draft = sample_drafts[0]

        # Create multiple runs
        run1 = SubmissionRun(
            draft_id=draft.id,
            run_status=RunStatus.FAILED,
            error_message='Network timeout',
        )
        run2 = SubmissionRun(
            draft_id=draft.id,
            run_status=RunStatus.COMPLETED,
            duration_ms=5000,
        )
        db.add(run1)
        db.add(run2)
        db.commit()

        detail = DashboardService.get_submission_detail(draft.id, db)

        assert len(detail['run_history']) == 2
        assert detail['run_history'][0]['status'] == 'failed'
        assert detail['run_history'][1]['status'] == 'completed'

    def test_get_detail_includes_metadata(self, db: Session, sample_candidate, sample_drafts):
        """Test detail includes job, candidate, and draft metadata."""
        draft = sample_drafts[0]
        job = sample_drafts[0].job_id
        detail = DashboardService.get_submission_detail(draft.id, db)

        assert detail['job_title'] == 'Senior Engineer'
        assert detail['company_name'] == 'TechCorp'
        assert detail['candidate_name'] == 'Alice Johnson'
        assert detail['fit_score'] == 85


class TestCompanyStats:
    """Test per-company statistics."""

    def test_get_company_stats_aggregation(self, db: Session, sample_candidate, sample_drafts):
        """Test stats aggregate by company."""
        stats = DashboardService.get_company_stats(sample_candidate.id, db)

        # 2 TechCorp, 1 StartupXYZ, 1 DataCo
        assert len(stats) == 3

        techcorp = [s for s in stats if s['company_name'] == 'TechCorp'][0]
        assert techcorp['total_applications'] == 2

    def test_get_company_stats_fit_scores(self, db: Session, sample_candidate, sample_drafts):
        """Test stats include average fit scores."""
        stats = DashboardService.get_company_stats(sample_candidate.id, db)

        techcorp = [s for s in stats if s['company_name'] == 'TechCorp'][0]
        # (85 + 75) / 2 = 80
        assert techcorp['avg_fit_score'] == 80.0

    def test_get_company_stats_status_distribution(self, db: Session, sample_candidate, sample_drafts):
        """Test stats include status distribution."""
        stats = DashboardService.get_company_stats(sample_candidate.id, db)

        techcorp = [s for s in stats if s['company_name'] == 'TechCorp'][0]
        assert techcorp['status_distribution']['draft'] == 1
        assert techcorp['status_distribution']['approved'] == 1
        assert techcorp['status_distribution']['submitted'] == 0

    def test_get_company_stats_sorted_by_count(self, db: Session, sample_candidate, sample_drafts):
        """Test stats are sorted by application count."""
        stats = DashboardService.get_company_stats(sample_candidate.id, db)

        # TechCorp has 2, others have 1
        assert stats[0]['company_name'] == 'TechCorp'
        assert stats[0]['total_applications'] == 2


class TestTimeline:
    """Test activity timeline."""

    def test_get_timeline_daily_counts(self, db: Session, sample_candidate, sample_drafts):
        """Test timeline aggregates by date."""
        timeline = DashboardService.get_timeline(sample_candidate.id, db, days=30)

        # Should have entries for 4 different days (today, -1, -3, -7)
        assert len(timeline) >= 3

    def test_get_timeline_time_window(self, db: Session, sample_candidate, sample_drafts):
        """Test timeline respects time window."""
        # Last 2 days should exclude the -7 day entry
        timeline = DashboardService.get_timeline(sample_candidate.id, db, days=2)

        # Only 3 drafts in last 2 days
        total_count = sum(entry['applications_created'] for entry in timeline)
        assert total_count == 3

    def test_get_timeline_ordered_chronologically(self, db: Session, sample_candidate, sample_drafts):
        """Test timeline entries are in chronological order."""
        timeline = DashboardService.get_timeline(sample_candidate.id, db, days=30)

        dates = [entry['date'] for entry in timeline]
        assert dates == sorted(dates)


class TestFilterValidation:
    """Test filter validation and edge cases."""

    def test_list_invalid_status_filter_ignored(self, db: Session, sample_candidate, sample_drafts):
        """Test invalid status filter is ignored gracefully."""
        submissions, total = DashboardService.list_submissions(
            sample_candidate.id, db, status_filter='invalid_status'
        )

        # Should return all since filter is invalid
        assert total == 4

    def test_list_company_filter_case_insensitive(self, db: Session, sample_candidate, sample_drafts):
        """Test company filter is case-insensitive."""
        submissions_lower, _ = DashboardService.list_submissions(
            sample_candidate.id, db, company_filter='techcorp'
        )
        submissions_upper, _ = DashboardService.list_submissions(
            sample_candidate.id, db, company_filter='TECHCORP'
        )

        assert len(submissions_lower) == 2
        assert len(submissions_upper) == 2

    def test_list_partial_company_match(self, db: Session, sample_candidate, sample_drafts):
        """Test company filter supports partial matching."""
        submissions, _ = DashboardService.list_submissions(
            sample_candidate.id, db, company_filter='Tech'
        )

        assert len(submissions) == 2


class TestEmptyResults:
    """Test handling of empty results."""

    def test_summary_empty_candidate(self, db: Session):
        """Test summary for candidate with no drafts."""
        summary = DashboardService.get_submission_summary(9999, db, days=30)

        assert summary['total_drafts'] == 0
        assert summary['avg_fit_score'] == 0
        assert summary['submission_completion_rate'] == 0.0

    def test_list_empty_candidate(self, db: Session):
        """Test list for candidate with no drafts."""
        submissions, total = DashboardService.list_submissions(9999, db)

        assert len(submissions) == 0
        assert total == 0

    def test_company_stats_empty_candidate(self, db: Session):
        """Test company stats for candidate with no drafts."""
        stats = DashboardService.get_company_stats(9999, db)

        assert len(stats) == 0

    def test_timeline_empty_candidate(self, db: Session):
        """Test timeline for candidate with no drafts."""
        timeline = DashboardService.get_timeline(9999, db, days=30)

        assert len(timeline) == 0
