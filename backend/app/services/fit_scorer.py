"""Fit scoring service for M1.4 - evaluates job compatibility against candidate profile."""

import logging
from typing import Optional
import json

from app.db_models import CandidateProfile, JobPosting, FitScore, Resume

logger = logging.getLogger(__name__)


class HardBlockerChecker:
    """Check for hard blocker conditions."""

    @staticmethod
    def check_work_authorization(candidate: CandidateProfile, job_description: Optional[str]) -> bool:
        """
        Detect work authorization mismatch.

        Hard blocker if:
        - Candidate needs sponsorship but job says "no sponsorship"
        - Candidate is not authorized (work_authorization is None and required fields missing)
        """
        if not candidate.work_authorization:
            return True  # Unknown work auth status is a blocker

        # Check job description for "no sponsorship" or "US citizen only"
        if job_description:
            job_desc_lower = job_description.lower()
            no_sponsor_indicators = [
                'no sponsorship',
                'citizens only',
                'must be authorized',
                'cannot sponsor',
                'no visa sponsorship',
            ]
            if candidate.work_authorization in ['NEED_SPONSORSHIP', 'NONE']:
                for indicator in no_sponsor_indicators:
                    if indicator in job_desc_lower:
                        return True

        return False

    @staticmethod
    def check_location_compatibility(candidate: CandidateProfile, job: JobPosting) -> bool:
        """
        Detect location incompatibility.

        Hard blocker if:
        - Job requires onsite in specific city, but candidate has "REMOTE_ONLY" preference and different location
        - Job is fully remote but candidate specified "ONSITE_ONLY"
        """
        if not candidate.location or not job.location:
            return False  # Cannot determine

        candidate_loc_lower = candidate.location.lower()
        job_loc_lower = job.location.lower()

        # Check remote preference
        if candidate.remote_preference and job_location:
            if candidate.remote_preference == 'REMOTE' and job_loc_lower not in ['remote', 'distributed']:
                return True  # Candidate wants remote, job is not

            if candidate.remote_preference == 'ONSITE' and job_loc_lower in ['remote', 'distributed']:
                return True  # Candidate wants onsite, job is remote

        # Check exact location mismatch for onsite jobs
        if job_loc_lower not in ['remote', 'distributed'] and candidate_loc_lower not in ['remote']:
            # Extract city names for comparison
            candidate_city = candidate_loc_lower.split(',')[0].strip()
            job_city = job_loc_lower.split(',')[0].strip()

            # Only flag if very different (not using fuzzy matching for hard blockers)
            if candidate_city and job_city and candidate_city != job_city:
                # Allow for some flexibility: if candidate has remote preference or job is hybrid
                if 'relocation' not in job_description.lower() if job.description else True:
                    return False  # Assume relocation possible unless job says no

        return False

    @staticmethod
    def check_seniority_mismatch(candidate: CandidateProfile, job_description: Optional[str]) -> bool:
        """
        Detect seniority level mismatch.

        Hard blocker if:
        - Job requires "10+ years" but candidate has <5 years
        - Job is "entry level" but candidate has 15+ years (overqualified might pass)
        """
        if not candidate.years_experience or not job_description:
            return False

        job_desc_lower = job_description.lower()

        # Check for extreme seniority requirements
        if '15+ years' in job_desc_lower or '15 years' in job_desc_lower:
            if candidate.years_experience < 12:
                return True

        if '20+ years' in job_desc_lower or '20 years' in job_desc_lower:
            if candidate.years_experience < 15:
                return True

        # Entry level bias (don't hard block if candidate is overqualified)
        if 'entry level' in job_desc_lower and candidate.years_experience >= 10:
            return False  # Not a blocker; candidate is qualified even if overqualified

        return False


class FitScoringEngine:
    """Calculate fit scores for candidate-job pairs."""

    def __init__(self):
        self.hard_blocker_checker = HardBlockerChecker()

    def calculate_fit_score(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
    ) -> dict:
        """
        Calculate comprehensive fit score for a candidate-job pair.

        Returns dict with:
        - overall_score: 0-100
        - recommendation: 'apply', 'review', 'skip'
        - dimensions: {title, skills, seniority, location, salary, work_auth}
        - hard_blockers: {work_auth, location, seniority}
        - explanation: str
        - reasoning_json: dict
        """

        # Check hard blockers first
        hard_blockers = {
            'work_auth': self.hard_blocker_checker.check_work_authorization(
                candidate,
                job.description
            ),
            'location': self.hard_blocker_checker.check_location_compatibility(candidate, job),
            'seniority': self.hard_blocker_checker.check_seniority_mismatch(candidate, job.description),
        }

        # Score dimensions
        dimensions = {
            'title_match_score': self._score_title_match(candidate, job),
            'skills_match_score': self._score_skills_match(candidate, job),
            'seniority_match_score': self._score_seniority_match(candidate, job),
            'location_match_score': self._score_location_match(candidate, job),
            'salary_match_score': self._score_salary_match(candidate, job),
            'work_auth_match_score': self._score_work_auth_match(candidate, job),
        }

        # Calculate overall score
        if any(hard_blockers.values()):
            # Hard blocker present -> recommendation is skip, score is low
            overall_score = 25
            recommendation = 'skip'
        else:
            # Average of dimension scores
            overall_score = int(sum(dimensions.values()) / len(dimensions))
            if overall_score >= 75:
                recommendation = 'apply'
            elif overall_score >= 50:
                recommendation = 'review'
            else:
                recommendation = 'skip'

        # Generate explanation
        explanation = self._generate_explanation(
            candidate,
            job,
            dimensions,
            hard_blockers,
            overall_score,
            recommendation
        )

        return {
            'overall_score': overall_score,
            'recommendation': recommendation,
            'dimensions': dimensions,
            'hard_blockers': hard_blockers,
            'explanation': explanation,
            'reasoning_json': {
                'dimensions': dimensions,
                'hard_blockers': hard_blockers,
                'scoring_rationale': self._get_scoring_rationale(candidate, job, dimensions, hard_blockers)
            }
        }

    def _score_title_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score how well job title matches candidate's target titles."""
        if not candidate.target_titles:
            return 70  # Neutral score if no targets specified

        job_title_lower = job.title.lower()
        match_score = 0
        best_match = 0

        for target in candidate.target_titles:
            target_lower = target.lower()
            # Exact substring match
            if target_lower in job_title_lower:
                best_match = max(best_match, 90)
            # Partial match on key words
            elif any(word in job_title_lower for word in target_lower.split()):
                best_match = max(best_match, 70)
            # Similar roles (heuristic)
            elif ('engineer' in target_lower and 'engineer' in job_title_lower) or \
                 ('manager' in target_lower and 'manager' in job_title_lower) or \
                 ('designer' in target_lower and 'designer' in job_title_lower):
                best_match = max(best_match, 75)

        return min(best_match or 60, 100)  # Default to 60 if no match

    def _score_skills_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score skills overlap between candidate and job."""
        if not job.description:
            return 70  # Neutral if no job description

        # Extract candidate skills from resume if available
        candidate_skills = []
        if candidate.primary_resume_id:
            # In production, would query resume parsed_data here
            pass

        job_desc_lower = job.description.lower()
        common_tech_skills = [
            'python', 'javascript', 'java', 'c++', 'typescript',
            'react', 'vue', 'angular', 'node', 'django',
            'sql', 'postgres', 'mongodb', 'firebase',
            'aws', 'gcp', 'azure', 'docker', 'kubernetes'
        ]

        # Count how many common skills appear in job description
        matched_skills = sum(1 for skill in common_tech_skills if skill in job_desc_lower)

        # Score based on mention frequency
        if matched_skills >= 5:
            return 85
        elif matched_skills >= 3:
            return 75
        elif matched_skills >= 1:
            return 65
        else:
            return 50  # No clear tech stack mentioned

    def _score_seniority_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score experience level match."""
        if not candidate.years_experience or not job.description:
            return 70

        job_desc_lower = job.description.lower()
        candidate_exp = candidate.years_experience

        # Extract required experience from job description
        if '20+ years' in job_desc_lower or '20 years' in job_desc_lower:
            required_exp = 20
            match_score = min(100, 50 + (candidate_exp / required_exp) * 50)
        elif '15+ years' in job_desc_lower or '15 years' in job_desc_lower:
            required_exp = 15
            match_score = min(100, 50 + (candidate_exp / required_exp) * 50)
        elif '10+ years' in job_desc_lower or '10 years' in job_desc_lower:
            required_exp = 10
            match_score = min(100, 50 + (candidate_exp / required_exp) * 50)
        elif '5+ years' in job_desc_lower or '5 years' in job_desc_lower:
            required_exp = 5
            match_score = 80 if candidate_exp >= required_exp else 60
        elif 'entry level' in job_desc_lower or 'junior' in job_desc_lower:
            # Entry level: match if candidate has <3 years
            match_score = 90 if candidate_exp <= 3 else 85
        else:
            # Mid-level assumed
            required_exp = 3
            match_score = 80 if candidate_exp >= required_exp else 70

        return int(match_score)

    def _score_location_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score location preference match."""
        if not job.location:
            return 70

        job_loc_lower = job.location.lower()

        # Remote jobs
        if job_loc_lower in ['remote', 'distributed', 'anywhere']:
            return 95 if candidate.remote_preference == 'REMOTE' else 80

        # Check candidate preference
        if not candidate.remote_preference:
            return 70

        if candidate.remote_preference == 'REMOTE':
            return 40  # Candidate wants remote, job is not

        if candidate.remote_preference == 'HYBRID' and 'hybrid' in job_loc_lower:
            return 90

        # Location match if candidate specified location
        if candidate.location:
            candidate_city = candidate.location.split(',')[0].lower().strip()
            job_city = job_loc_lower.split(',')[0].lower().strip()
            if candidate_city == job_city:
                return 95

        return 65  # Acceptable but not ideal

    def _score_salary_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score salary expectation alignment."""
        if not candidate.salary_floor_usd or not job.description:
            return 70

        job_desc_lower = job.description.lower()

        # Try to extract salary range from job description (simplified heuristic)
        # Look for patterns like "$100k", "$100,000", "100k salary"
        import re
        salary_pattern = r'\$?(\d+)[,k]?(?:\s*[-–]\s*\$?(\d+))?[,k]?'
        matches = re.findall(salary_pattern, job_desc_lower)

        if not matches:
            return 70  # No salary info

        # Use first salary mention as estimate
        salary_str = matches[0][0]
        try:
            # Handle "100k" format
            if 'k' in job_desc_lower:
                salary_estimate = int(salary_str) * 1000
            else:
                salary_estimate = int(salary_str)

            if salary_estimate >= candidate.salary_floor_usd:
                return 95
            elif salary_estimate >= candidate.salary_floor_usd * 0.85:
                return 75
            else:
                return 50  # Below expectation
        except (ValueError, IndexError):
            return 70

    def _score_work_auth_match(self, candidate: CandidateProfile, job: JobPosting) -> int:
        """Score work authorization compatibility."""
        if not candidate.work_authorization:
            return 50  # Unknown work auth is risky

        if candidate.work_authorization in ['US_CITIZEN', 'GREEN_CARD']:
            return 95  # Fully eligible

        if candidate.work_authorization == 'NEED_SPONSORSHIP':
            if job.description and 'sponsorship' in job.description.lower():
                return 85
            else:
                return 60  # Sponsorship not mentioned

        return 70  # Default for other auth types

    def _generate_explanation(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        dimensions: dict,
        hard_blockers: dict,
        overall_score: int,
        recommendation: str
    ) -> str:
        """Generate human-readable explanation of the fit score."""
        lines = []

        # Recommendation headline
        if recommendation == 'apply':
            lines.append(f'✅ Strong Match ({overall_score}/100) - Recommended to Apply')
        elif recommendation == 'review':
            lines.append(f'⚠️ Moderate Match ({overall_score}/100) - Worth Reviewing')
        else:
            lines.append(f'❌ Poor Match ({overall_score}/100) - Consider Skipping')

        # Hard blockers
        if any(hard_blockers.values()):
            blocker_reasons = []
            if hard_blockers['work_auth']:
                blocker_reasons.append('work authorization')
            if hard_blockers['location']:
                blocker_reasons.append('location incompatibility')
            if hard_blockers['seniority']:
                blocker_reasons.append('seniority mismatch')
            lines.append(f'Hard Blockers: {", ".join(blocker_reasons)}')

        # Top 2 dimension strengths
        top_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)[:2]
        if top_dims:
            lines.append(f'Strengths: {", ".join(dim.replace("_", " ").title() + f" ({score})" for dim, score in top_dims)}')

        # Bottom dimension weakness
        weak_dims = sorted(dimensions.items(), key=lambda x: x[1])[:1]
        if weak_dims and weak_dims[0][1] < 60:
            lines.append(f'Area of Concern: {weak_dims[0][0].replace("_", " ").title()} ({weak_dims[0][1]})')

        return '\n'.join(lines)

    def _get_scoring_rationale(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        dimensions: dict,
        hard_blockers: dict
    ) -> dict:
        """Generate detailed scoring rationale for transparency."""
        return {
            'title_match': {
                'score': dimensions['title_match_score'],
                'candidate_targets': candidate.target_titles or [],
                'job_title': job.title
            },
            'location_fit': {
                'score': dimensions['location_match_score'],
                'candidate_preference': candidate.remote_preference,
                'job_location': job.location
            },
            'work_auth': {
                'score': dimensions['work_auth_match_score'],
                'hard_blocker': hard_blockers['work_auth'],
                'candidate_auth': candidate.work_authorization
            },
            'seniority': {
                'score': dimensions['seniority_match_score'],
                'hard_blocker': hard_blockers['seniority'],
                'candidate_years': candidate.years_experience
            }
        }
