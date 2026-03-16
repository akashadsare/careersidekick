"""M1.8: Applications Dashboard Service

Dashboard queries and analytics for submitted applications.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from ..db_models import (
    ApplicationDraft,
    CandidateProfile,
    DraftStatus,
    JobPosting,
    RunStatus,
    SubmissionRun,
)


class DashboardService:
    """Query service for applications dashboard."""

    @staticmethod
    def get_submission_summary(
        candidate_id: int,
        db: Session,
        days: int = 30,
    ) -> dict:
        """
        Get submission summary for a candidate over a time period.

        Args:
            candidate_id: Candidate profile ID
            db: SQLAlchemy session
            days: Time window in days

        Returns:
            dict with counts by status, avg fit score, completion rate
        """
        window_start = datetime.now(UTC) - timedelta(days=days)

        # Get all drafts in window
        drafts = db.query(ApplicationDraft).filter(
            and_(
                ApplicationDraft.candidate_id == candidate_id,
                ApplicationDraft.created_at >= window_start,
            )
        ).all()

        # Count by status
        by_status = {
            'draft': sum(1 for d in drafts if d.status == DraftStatus.DRAFT),
            'approved': sum(1 for d in drafts if d.status == DraftStatus.APPROVED),
            'submitted': sum(1 for d in drafts if d.status == DraftStatus.SUBMITTED),
            'failed': sum(1 for d in drafts if d.status == DraftStatus.FAILED),
        }

        # Fit score stats
        fit_scores = [d.fit_score for d in drafts if d.fit_score]
        avg_fit_score = sum(fit_scores) / len(fit_scores) if fit_scores else 0
        max_fit_score = max(fit_scores) if fit_scores else 0

        # Submission completion rate
        submitted_count = by_status['submitted']
        total_count = len(drafts)
        completion_rate = (submitted_count / total_count * 100) if total_count > 0 else 0.0

        # Query runs for submitted drafts
        submitted_drafts = [d for d in drafts if d.status == DraftStatus.SUBMITTED]
        successful_runs = 0
        if submitted_drafts:
            successful_runs = db.query(SubmissionRun).filter(
                and_(
                    SubmissionRun.draft_id.in_([d.id for d in submitted_drafts]),
                    SubmissionRun.run_status == RunStatus.COMPLETED,
                )
            ).count()

        return {
            'window_days': days,
            'total_drafts': total_count,
            'by_status': by_status,
            'avg_fit_score': round(avg_fit_score, 2),
            'max_fit_score': max_fit_score,
            'submission_completion_rate': round(completion_rate, 2),
            'successful_submissions': successful_runs,
        }

    @staticmethod
    def list_submissions(
        candidate_id: int,
        db: Session,
        status_filter: Optional[str] = None,
        company_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        List submissions with filtering and pagination.

        Args:
            candidate_id: Candidate profile ID
            db: SQLAlchemy session
            status_filter: Filter by status (draft|approved|submitted|failed)
            company_filter: Filter by company name (substring match)
            limit: Results per page
            offset: Pagination offset

        Returns:
            Tuple of (list of submission dicts, total count)
        """
        query = (
            db.query(
                ApplicationDraft,
                JobPosting,
                CandidateProfile,
                SubmissionRun,
            )
            .join(JobPosting, ApplicationDraft.job_id == JobPosting.id)
            .join(CandidateProfile, ApplicationDraft.candidate_id == CandidateProfile.id)
            .outerjoin(SubmissionRun, ApplicationDraft.id == SubmissionRun.draft_id)
            .filter(ApplicationDraft.candidate_id == candidate_id)
        )

        if status_filter:
            try:
                status = DraftStatus(status_filter)
                query = query.filter(ApplicationDraft.status == status)
            except ValueError:
                pass

        if company_filter:
            query = query.filter(JobPosting.company_name.ilike(f'%{company_filter}%'))

        total_count = query.count()

        rows = (
            query.order_by(ApplicationDraft.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        submissions = []
        for draft, job, candidate, run in rows:
            submission = {
                'draft_id': draft.id,
                'candidate_id': candidate.id,
                'candidate_name': candidate.full_name,
                'job_id': job.id,
                'job_title': job.title,
                'company_name': job.company_name,
                'location': job.location,
                'ats_type': job.ats_type,
                'fit_score': draft.fit_score,
                'draft_status': draft.status.value,
                'created_at': draft.created_at,
                'run_id': run.id if run else None,
                'run_status': run.run_status.value if run else None,
                'run_duration_ms': run.duration_ms if run else None,
                'completed_at': run.finished_at if run else None,
            }
            submissions.append(submission)

        return submissions, total_count

    @staticmethod
    def get_submission_detail(draft_id: int, db: Session) -> dict:
        """
        Get full details for a single submission including run history.

        Args:
            draft_id: ApplicationDraft ID
            db: SQLAlchemy session

        Returns:
            dict with all submission details and run history
        """
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == draft_id).first()
        if not draft:
            raise ValueError(f'Draft {draft_id} not found')

        job = db.query(JobPosting).filter(JobPosting.id == draft.job_id).first()
        candidate = db.query(CandidateProfile).filter(CandidateProfile.id == draft.candidate_id).first()

        # Get all runs for this draft
        runs = db.query(SubmissionRun).filter(SubmissionRun.draft_id == draft_id).all()

        return {
            'draft_id': draft.id,
            'candidate_id': candidate.id,
            'candidate_name': candidate.full_name,
            'candidate_email': candidate.email,
            'job_id': job.id,
            'job_title': job.title,
            'company_name': job.company_name,
            'job_url': job.apply_url or job.source_url,
            'location': job.location,
            'ats_type': job.ats_type,
            'fit_score': draft.fit_score,
            'answers': draft.answers_json.get('answers', []),
            'cover_note': draft.cover_note,
            'draft_status': draft.status.value,
            'created_at': draft.created_at,
            'run_history': [
                {
                    'run_id': run.id,
                    'status': run.run_status.value,
                    'started_at': run.started_at,
                    'finished_at': run.finished_at,
                    'duration_ms': run.duration_ms,
                    'error_message': run.error_message,
                    'result_json': run.result_json,
                }
                for run in runs
            ],
        }

    @staticmethod
    def get_company_stats(candidate_id: int, db: Session) -> list[dict]:
        """
        Get submission statistics grouped by company.

        Args:
            candidate_id: Candidate profile ID
            db: SQLAlchemy session

        Returns:
            list of company stats (count, status distribution, avg fit score)
        """
        query = (
            db.query(
                JobPosting.company_name,
                func.count(ApplicationDraft.id).label('total_applications'),
                func.avg(ApplicationDraft.fit_score).label('avg_fit_score'),
            )
            .join(JobPosting, ApplicationDraft.job_id == JobPosting.id)
            .filter(ApplicationDraft.candidate_id == candidate_id)
            .group_by(JobPosting.company_name)
            .order_by(func.count(ApplicationDraft.id).desc())
        )

        stats = []
        for company_name, total_applications, avg_fit_score in query:
            # Count by status for this company
            company_drafts = (
                db.query(ApplicationDraft)
                .join(JobPosting, ApplicationDraft.job_id == JobPosting.id)
                .filter(
                    and_(
                        ApplicationDraft.candidate_id == candidate_id,
                        JobPosting.company_name == company_name,
                    )
                )
                .all()
            )

            status_counts = {
                'draft': sum(1 for d in company_drafts if d.status == DraftStatus.DRAFT),
                'approved': sum(1 for d in company_drafts if d.status == DraftStatus.APPROVED),
                'submitted': sum(1 for d in company_drafts if d.status == DraftStatus.SUBMITTED),
                'failed': sum(1 for d in company_drafts if d.status == DraftStatus.FAILED),
            }

            stats.append({
                'company_name': company_name,
                'total_applications': total_applications,
                'avg_fit_score': round(float(avg_fit_score) if avg_fit_score else 0, 2),
                'status_distribution': status_counts,
            })

        return stats

    @staticmethod
    def get_timeline(candidate_id: int, db: Session, days: int = 30) -> list[dict]:
        """
        Get timeline of submissions (activity over time).

        Args:
            candidate_id: Candidate profile ID
            db: SQLAlchemy session
            days: Time window

        Returns:
            list of daily activity records
        """
        window_start = datetime.now(UTC) - timedelta(days=days)

        query = (
            db.query(
                func.date(ApplicationDraft.created_at).label('date'),
                func.count(ApplicationDraft.id).label('count'),
            )
            .filter(
                and_(
                    ApplicationDraft.candidate_id == candidate_id,
                    ApplicationDraft.created_at >= window_start,
                )
            )
            .group_by(func.date(ApplicationDraft.created_at))
            .order_by(func.date(ApplicationDraft.created_at))
        )

        timeline = []
        for date, count in query:
            timeline.append({
                'date': date.isoformat() if date else None,
                'applications_created': count,
            })

        return timeline
