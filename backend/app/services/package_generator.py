"""M1.5: Application Package Generation Service

Generates customized application packages by:
1. Matching job questions to candidate's answer library
2. Generating field answers using profile + previous answers
3. Flagging unanswerable questions for manual review
4. Creating cover note (3-5 sentences) contextualized to job & candidate
"""

import json
import re
from datetime import UTC, datetime

from ..db_models import AnswerLibraryQuestion, CandidateAnswer, CandidateProfile, FitScore, JobPosting


class PackageGenerationService:
    """Generate application packages with fit-contextualized answers and cover notes."""

    # Common screening question patterns across ATS platforms
    CANDIDATE_QUESTION_PATTERNS = {
        'work_auth': [
            r'.*authorized.*work.*country.*',
            r'.*visa.*sponsor.*',
            r'.*work.*permit.*',
            r'.*work.*authorization.*',
        ],
        'years_experience': [
            r'.*years?.*experience.*',
            r'.*how.*long.*',
            r'.*total.*experience.*',
        ],
        'remote_preference': [
            r'.*remote.*work.*',
            r'.*work.*location.*',
            r'.*onsite.*hybrid.*',
            r'.*willing.*relocate.*',
        ],
        'culture': [
            r'.*team.*work.*',
            r'.*collaboration.*',
            r'.*communication.*',
            r'.*culture.*fit.*',
        ],
        'technical_skills': [
            r'.*skill.*',
            r'.*programming.*',
            r'.*languages?.*',
            r'.*frameworks?.*',
            r'.*tools?.*',
        ],
        'motivation': [
            r'.*why.*interested.*',
            r'.*interested.*role.*',
            r'.*why.*apply.*',
            r'.*motivated.*',
        ],
    }

    def __init__(self):
        """Initialize package generation service."""
        pass

    def generate_package(self, candidate_id: int, job_id: int, db) -> dict:
        """
        Generate application package for (candidate_id, job_id).

        Args:
            candidate_id: Candidate profile ID
            job_id: Job posting ID
            db: SQLAlchemy session

        Returns:
            dict with keys:
            - package_id (int): ApplicationDraft.id
            - candidate_id (int)
            - job_id (int)
            - fit_score (int): From M1.4 FitScore or 0 if none
            - answers (list): Question-answer pairs with provenance
            - cover_note (str): 3-5 sentence contextualized note
            - needs_review_flags (list): Questions flagged as unanswerable
        """
        # Retrieve entities
        candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
        if not candidate:
            raise ValueError(f'Candidate {candidate_id} not found')

        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if not job:
            raise ValueError(f'Job {job_id} not found')

        # Retrieve M1.4 fit score if available
        fit_score_orm = db.query(FitScore).filter(
            FitScore.candidate_id == candidate_id, FitScore.job_id == job_id
        ).first()
        fit_score = fit_score_orm.overall_score if fit_score_orm else 0

        # Generate answers for screening questions
        answers, needs_review_flags = self._generate_answers(candidate, job, db)

        # Generate contextualized cover note
        cover_note = self._generate_cover_note(candidate, job, fit_score)

        # Store as ApplicationDraft
        from ..db_models import ApplicationDraft, DraftStatus

        draft = ApplicationDraft(
            candidate_id=candidate_id,
            job_id=job_id,
            fit_score=fit_score,
            answers_json={'answers': answers, 'needs_review_flags': needs_review_flags},
            cover_note=cover_note,
            status=DraftStatus.DRAFT,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        return {
            'package_id': draft.id,
            'candidate_id': candidate_id,
            'job_id': job_id,
            'fit_score': fit_score,
            'answers': answers,
            'cover_note': cover_note,
            'needs_review_flags': needs_review_flags,
        }

    def _generate_answers(self, candidate: CandidateProfile, job: JobPosting, db) -> tuple[list[dict], list[dict]]:
        """
        Generate answers for screening questions.

        Returns:
            (answers, needs_review_flags)
            answers: List of {"question", "answer", "provenance"}
            needs_review_flags: List of {"question", "reason", "question_id"}
        """
        answers = []
        needs_review_flags = []

        # Infer likely screening questions for this job based on ATS type and job description
        likely_questions = self._infer_screening_questions(job, db)

        for question in likely_questions:
            category = question.question_category
            answer = self._match_candidate_answer(candidate, category, db)

            if answer:
                answers.append({
                    'question': question.question_text,
                    'answer': answer['answer_text'],
                    'provenance': answer['provenance'],
                    'question_id': question.id,
                })
            else:
                needs_review_flags.append({
                    'question': question.question_text,
                    'reason': f'No candidate answer found for category: {category}',
                    'question_id': question.id,
                })

        return answers, needs_review_flags

    def _infer_screening_questions(self, job: JobPosting, db) -> list[AnswerLibraryQuestion]:
        """
        Infer likely screening questions for a job.

        Strategy:
        1. If job has ATS type, filter answer_library questions for that ATS
        2. Prioritize by frequency_rank (lower = more common)
        3. Return top 5-8 questions
        """
        query = db.query(AnswerLibraryQuestion)

        # Filter by ATS type if available
        if job.ats_type:
            ats_lower = job.ats_type.lower()
            query = query.filter(AnswerLibraryQuestion.portal_types.contains([ats_lower]))

        # Sort by frequency rank (lower = more common)
        questions = query.order_by(AnswerLibraryQuestion.frequency_rank).limit(8).all()

        # If no questions found for specific ATS, fetch top questions globally
        if not questions:
            questions = db.query(AnswerLibraryQuestion).order_by(
                AnswerLibraryQuestion.frequency_rank
            ).limit(8).all()

        return questions

    def _match_candidate_answer(self, candidate: CandidateProfile, category: str, db) -> dict | None:
        """
        Match candidate's answer for a question category.

        Strategy:
        1. Check if candidate has explicit answer in CandidateAnswer table for this category
        2. If not, try to infer from resume (parsed_data)
        3. If not, try to generate from profile fields
        4. Return None if unanswerable
        """
        # Strategy 1: Explicit candidate answer
        explicit_answer = db.query(CandidateAnswer).join(
            AnswerLibraryQuestion, CandidateAnswer.library_question_id == AnswerLibraryQuestion.id
        ).filter(
            CandidateAnswer.candidate_id == candidate.id,
            AnswerLibraryQuestion.question_category == category,
        ).first()

        if explicit_answer:
            return {
                'answer_text': explicit_answer.answer_text,
                'provenance': 'candidate_answer',
            }

        # Strategy 2: Infer from resume parsed_data
        if candidate.resumes and candidate.resumes[0].parsed_data:
            resume_answer = self._extract_from_resume(candidate.resumes[0].parsed_data, category)
            if resume_answer:
                return {
                    'answer_text': resume_answer,
                    'provenance': 'resume',
                }

        # Strategy 3: Infer from profile fields
        profile_answer = self._generate_from_profile(candidate, category)
        if profile_answer:
            return {
                'answer_text': profile_answer,
                'provenance': 'profile',
            }

        return None

    def _extract_from_resume(self, parsed_data: dict, category: str) -> str | None:
        """Extract relevant information from parsed resume data."""
        category_lower = category.lower()

        if category_lower in ['work_auth', 'work_authorization']:
            # Default to US work auth if not specified
            return 'I am authorized to work in the United States.'

        if category_lower in ['years_experience', 'experience']:
            experience_years = parsed_data.get('years_of_experience')
            if experience_years:
                return f'I have {experience_years}+ years of professional experience.'
            return None

        if category_lower in ['technical_skills', 'skills']:
            skills = parsed_data.get('skills')
            if skills and len(skills) > 0:
                skills_str = ', '.join(skills[:5])  # Top 5 skills
                return f'My key technical skills include: {skills_str}.'
            return None

        return None

    def _generate_from_profile(self, candidate: CandidateProfile, category: str) -> str | None:
        """Generate answer from candidate profile fields."""
        category_lower = category.lower()

        if category_lower in ['work_auth', 'work_authorization']:
            return 'I am authorized to work in the United States.'

        if category_lower in ['remote_preference', 'work_location']:
            if candidate.location:
                return f'I am located in {candidate.location} and am open to remote, hybrid, or onsite roles.'
            return 'I am open to remote, hybrid, or onsite roles.'

        if category_lower in ['culture', 'collaboration']:
            return 'I value strong collaboration, clear communication, and continuous learning. I thrive in teams that prioritize both technical excellence and interpersonal growth.'

        if category_lower in ['motivation']:
            return f'I am excited to contribute to a team that values innovation and impact. I am particularly interested in roles where I can leverage my experience and continue growing as an engineer.'

        return None

    def _generate_cover_note(self, candidate: CandidateProfile, job: JobPosting, fit_score: int) -> str:
        """Generate contextualized cover note (3-5 sentences)."""
        lines = []

        # Sentence 1: Opening with role & company
        lines.append(
            f'I am excited to apply for the {job.title} role at {job.company_name}.'
        )

        # Sentence 2: Fit context from M1.4
        if fit_score >= 75:
            lines.append(
                'My experience and skills are a strong match for this position, and I am confident I can make an immediate impact.'
            )
        elif fit_score >= 50:
            lines.append(
                'My background aligns well with many aspects of this role, and I am eager to learn and grow in this opportunity.'
            )
        else:
            lines.append(
                'I am interested in this opportunity and believe my skills can add value to your team.'
            )

        # Sentence 3: Location/preference context
        if job.location and 'remote' in job.location.lower():
            if candidate.location:
                lines.append(f'Based in {candidate.location}, I am well-positioned for this remote role.')
            else:
                lines.append('I am available for this remote role.')
        elif job.location and candidate.location:
            lines.append(f'Based in {candidate.location}, I am open to the work arrangement for this role.')

        # Sentence 4: Closing
        lines.append(
            'I would welcome the opportunity to discuss how I can contribute to your team\'s success.'
        )

        return ' '.join(lines)


def generate_application_package(candidate_id: int, job_id: int, db) -> dict:
    """Public interface for package generation."""
    service = PackageGenerationService()
    return service.generate_package(candidate_id, job_id, db)
