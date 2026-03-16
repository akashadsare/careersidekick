"""M1.7: Submission Execution Service

Orchestrates TinyFish browser automation to submit applications.

Flow:
1. Retrieve approved ApplicationDraft
2. Load TinyFish portal prompt for ATS type
3. Call TinyFish REST API with browser automation goal
4. Stream results via SSE (server-sent events)
5. Parse completion result
6. Store SubmissionRun with success/failure
7. Transition ApplicationDraft to submitted/failed
"""

import json
import re
from datetime import UTC, datetime
from typing import AsyncGenerator, Optional

import httpx

from ..db_models import ApplicationDraft, DraftStatus, JobPosting, SubmissionRun, RunStatus


class PortalPromptBuilder:
    """Build TinyFish goal prompts for different ATS platforms."""

    # Portal-specific field mappings and instructions
    PORTAL_CONFIGS = {
        'greenhouse': {
            'name': 'Greenhouse',
            'instructions': '''Navigate and fill the Greenhouse job application form:
1. Fill full name, email, phone if present
2. For screening questions: answer with provided text or skip if N/A
3. Upload resume from provided URL
4. Do NOT click final submit - stop at review screen
5. Return JSON with filled fields and success status''',
            'required_fields': ['full_name', 'email', 'work_auth'],
        },
        'lever': {
            'name': 'Lever',
            'instructions': '''Navigate and fill the Lever job application form:
1. Fill name, email, phone
2. Answer employment type and work authorization questions
3. Upload resume
4. Do NOT submit - stop at review
5. Return fields filled and status''',
            'required_fields': ['full_name', 'email'],
        },
        'linkedin': {
            'name': 'LinkedIn Easy Apply',
            'instructions': '''Navigate LinkedIn Easy Apply form:
1. Fill auto-populated fields
2. Answer custom questions if present
3. Review all fields
4. Do NOT click submit
5. Show final state with all fields''',
            'required_fields': ['full_name', 'email'],
        },
    }

    @staticmethod
    def build_submission_goal(job_url: str, ats_type: str, candidate_data: dict, draft_data: dict) -> str:
        """
        Build TinyFish goal prompt for job application submission.

        Args:
            job_url: Job posting URL (apply_url)
            ats_type: ATS platform type (greenhouse, lever, linkedin, etc.)
            candidate_data: Candidate profile fields
            draft_data: ApplicationDraft with answers and cover note

        Returns:
            Goal prompt for TinyFish browser automation
        """
        portal_config = PortalPromptBuilder.PORTAL_CONFIGS.get(ats_type.lower(), {})
        portal_name = portal_config.get('name', ats_type)

        # Extract answers from draft
        answers_json = draft_data.get('answers_json', {})
        answers = answers_json.get('answers', [])

        # Build field values mapping
        fields = {
            'full_name': candidate_data.get('full_name'),
            'email': candidate_data.get('email'),
            'phone': candidate_data.get('phone'),
            'location': candidate_data.get('location'),
            'work_auth': next(
                (a.get('answer') for a in answers if 'authorized' in a.get('question', '').lower()),
                None,
            ),
            'cover_note': draft_data.get('cover_note'),
        }

        # Build goal prompt
        goal = f"""You are applying to a job on {portal_name}.

JOB URL: {job_url}

APPLICANT INFORMATION:
- Name: {fields['full_name']}
- Email: {fields['email']}
- Phone: {fields['phone']}
- Location: {fields['location']}
- Work Authorization: {fields['work_auth']}

SCREENING ANSWERS:
"""
        for answer in answers:
            goal += f"\nQ: {answer.get('question')}\nA: {answer.get('answer')}\n"

        goal += f"""
COVER NOTE/MESSAGE:
{fields['cover_note']}

INSTRUCTIONS:
{portal_config.get('instructions', 'Fill the application form completely.')}

RETURN REQUIRED:
When done, return JSON with:
{{
  "status": "success" | "failure",
  "error_code": null or error identifier,
  "error_message": human readable error or null,
  "reached_review_screen": true/false,
  "fields_filled": {{"full_name": "value", "email": "value", ...}},
  "final_screenshot": "base64 or URL",
  "duration_ms": seconds * 1000
}}
"""
        return goal


class TinyFishExecutionService:
    """Execute job applications via TinyFish browser automation."""

    def __init__(self, tinyfish_api_key: str, tinyfish_api_base: str = 'https://api.tinyfish.ai'):
        """Initialize with TinyFish API credentials."""
        self.api_key = tinyfish_api_key
        self.api_base = tinyfish_api_base
        self.client = httpx.AsyncClient()

    async def submit_application(
        self, approved_draft_id: int, db, resume_url: str | None = None
    ) -> dict:
        """
        Submit application via TinyFish browser automation.

        Args:
            approved_draft_id: ApplicationDraft.id (must be status=approved)
            db: SQLAlchemy session
            resume_url: Optional resume S3 URL (if not in candidate resume)

        Returns:
            dict with submission result
        """
        # Retrieve draft, candidate, job
        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == approved_draft_id).first()
        if not draft:
            raise ValueError(f'Draft {approved_draft_id} not found')

        if draft.status != DraftStatus.APPROVED:
            raise ValueError(f'Draft {approved_draft_id} is not approved (status: {draft.status})')

        job = db.query(JobPosting).filter(JobPosting.id == draft.job_id).first()
        if not job:
            raise ValueError('Job not found')

        if not job.apply_url:
            raise ValueError('Job has no apply_url')

        # Build TinyFish goal
        candidate_data = {
            'full_name': draft.candidate.full_name,
            'email': draft.candidate.email,
            'phone': draft.candidate.phone,
            'location': draft.candidate.location,
        }

        draft_data = {
            'answers_json': draft.answers_json or {},
            'cover_note': draft.cover_note,
        }

        goal = PortalPromptBuilder.build_submission_goal(job.apply_url, job.ats_type or 'unknown', candidate_data, draft_data)

        # Create SubmissionRun
        run = SubmissionRun(
            draft_id=draft.id,
            run_status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Call TinyFish API (streaming)
        try:
            result = await self._call_tinyfish_streaming(goal, job.apply_url, run.id)
            
            # Update run with result
            run.run_status = RunStatus.COMPLETED if result.get('status') == 'success' else RunStatus.FAILED
            run.finished_at = datetime.now(UTC)
            run.duration_ms = result.get('duration_ms')
            run.result_json = result
            run.error_message = result.get('error_message')

            db.add(run)

            # Update draft status
            if result.get('status') == 'success' and result.get('reached_review_screen'):
                draft.status = DraftStatus.SUBMITTED
            else:
                draft.status = DraftStatus.FAILED

            db.add(draft)
            db.commit()

            return {
                'run_id': run.id,
                'draft_id': draft.id,
                'status': result.get('status'),
                'error_code': result.get('error_code'),
                'error_message': result.get('error_message'),
                'reached_review_screen': result.get('reached_review_screen'),
                'duration_ms': run.duration_ms,
            }
        except Exception as e:
            # Mark as failed
            run.run_status = RunStatus.FAILED
            run.finished_at = datetime.now(UTC)
            run.error_message = str(e)
            db.add(run)

            draft.status = DraftStatus.FAILED
            db.add(draft)
            db.commit()

            raise

    async def _call_tinyfish_streaming(self, goal: str, url: str, run_id: int) -> dict:
        """
        Call TinyFish API with streaming result collection.

        Args:
            goal: Browser automation goal
            url: Target URL
            run_id: SubmissionRun ID for tracking

        Returns:
            Parsed final result JSON
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'url': url,
            'goal': goal,
            'browser_profile': 'lite',
            'stream': True,
        }

        # Stream response from TinyFish
        final_result = {}
        try:
            async with self.client.stream('POST', f'{self.api_base}/v1/automation', json=payload, headers=headers) as response:
                if response.status_code != 200:
                    raise ValueError(f'TinyFish API error: {response.status_code}')

                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            # Collect final result
                            if data.get('type') == 'complete':
                                final_result = data.get('result', {})
                        except json.JSONDecodeError:
                            pass
        except httpx.RequestError as e:
            return {
                'status': 'failure',
                'error_code': 'network_error',
                'error_message': str(e),
                'reached_review_screen': False,
            }

        return final_result

    async def get_submission_status(self, run_id: int, db) -> dict:
        """Get submission run status."""
        run = db.query(SubmissionRun).filter(SubmissionRun.id == run_id).first()
        if not run:
            raise ValueError(f'Run {run_id} not found')

        return {
            'run_id': run.id,
            'draft_id': run.draft_id,
            'status': run.run_status.value,
            'started_at': run.started_at,
            'finished_at': run.finished_at,
            'duration_ms': run.duration_ms,
            'result_json': run.result_json,
            'error_message': run.error_message,
        }
