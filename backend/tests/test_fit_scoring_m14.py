"""Tests for M1.4 fit scoring."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, UTC

from app.db_models import CandidateProfile, JobPosting, FitScore
from app.services.fit_scorer import FitScoringEngine, HardBlockerChecker


class TestHardBlockerChecker:
    """Test hard blocker detection."""

    def test_work_auth_blocker_missing_auth(self):
        """Test that missing work authorization is a blocker."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.work_authorization = None
        
        checker = HardBlockerChecker()
        assert checker.check_work_authorization(candidate, None) is True

    def test_work_auth_blocker_sponsorship_needed(self):
        """Test that sponsorship mismatch is blocked."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.work_authorization = 'NEED_SPONSORSHIP'
        
        job_desc = 'No sponsorship. US citizens only.'
        
        checker = HardBlockerChecker()
        assert checker.check_work_authorization(candidate, job_desc) is True

    def test_work_auth_ok_for_eligible(self):
        """Test that US citizens are not blocked."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.work_authorization = 'US_CITIZEN'
        
        checker = HardBlockerChecker()
        assert checker.check_work_authorization(candidate, None) is False

    def test_seniority_blocker_huge_gap(self):
        """Test hard blocker for large seniority gap."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.years_experience = 2
        
        job_desc = 'Requires 20+ years of experience in the field.'
        
        checker = HardBlockerChecker()
        assert checker.check_seniority_mismatch(candidate, job_desc) is True

    def test_seniority_ok_for_experienced(self):
        """Test no blocker for experienced candidate on entry level role."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.years_experience = 15
        
        job_desc = 'Entry level position for recent graduates.'
        
        checker = HardBlockerChecker()
        # Overqualified is not a blocker
        assert checker.check_seniority_mismatch(candidate, job_desc) is False

    def test_location_blocker_remote_only_candidate_onsite_job(self):
        """Test blocker when remote-only candidate faces onsite job."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.location = 'San Francisco, CA'
        candidate.remote_preference = 'REMOTE'
        
        job = MagicMock(spec=JobPosting)
        job.location = 'New York, NY'
        job.description = 'Onsite role'
        
        checker = HardBlockerChecker()
        result = checker.check_location_compatibility(candidate, job)
        assert result is True  # Blocker expected


class TestFitScoringEngine:
    """Test fit scoring calculations."""

    def test_score_title_exact_match(self):
        """Test perfect title match scoring."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.target_titles = ['Software Engineer']
        candidate.years_experience = 5
        candidate.salary_floor_usd = 100000
        candidate.remote_preference = 'REMOTE'
        candidate.work_authorization = 'US_CITIZEN'
        candidate.location = 'Any'
        candidate.primary_resume_id = None

        job = MagicMock(spec=JobPosting)
        job.title = 'Senior Software Engineer'
        job.location = 'Remote'
        job.description = 'Looking for a senior software engineer. No sponsorship.'

        engine = FitScoringEngine()
        score = engine._score_title_match(candidate, job)
        assert score >= 85  # High match for "Software Engineer" in title

    def test_score_title_no_match(self):
        """Test poor title match scoring."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.target_titles = ['Software Engineer']

        job = MagicMock(spec=JobPosting)
        job.title = 'Barista - Downtown Cafe'

        engine = FitScoringEngine()
        score = engine._score_title_match(candidate, job)
        assert score < 70  # Low match

    def test_full_score_calculation_strong_match(self):
        """Test full calculation for strong match."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.full_name = 'John Doe'
        candidate.target_titles = ['Software Engineer', 'Backend Engineer']
        candidate.years_experience = 5
        candidate.salary_floor_usd = 120000
        candidate.remote_preference = 'REMOTE'
        candidate.work_authorization = 'US_CITIZEN'
        candidate.location = 'Bay Area, CA'
        candidate.primary_resume_id = None

        job = MagicMock(spec=JobPosting)
        job.title = 'Staff Software Engineer'
        job.company_name = 'TechCorp'
        job.location = 'Remote'
        job.description = (
            'We are hiring a Staff Software Engineer. Requirements: '
            '5+ years Python, JavaScript, React, Docker, Kubernetes. '
            'Salary: $150,000-$200,000. Remote position. '
            'US citizens or green card holders only.'
        )

        engine = FitScoringEngine()
        result = engine.calculate_fit_score(candidate, job)

        assert result['overall_score'] >= 75
        assert result['recommendation'] == 'apply'
        assert not result['hard_blockers']['work_auth']
        assert not result['hard_blockers']['location']
        assert result['explanation'] is not None

    def test_full_score_calculation_with_blocker(self):
        """Test calculation where hard blocker is present."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.full_name = 'Jane Smith'
        candidate.target_titles = ['QA Engineer']
        candidate.years_experience = 25
        candidate.salary_floor_usd = 100000
        candidate.remote_preference = 'ONSITE'
        candidate.work_authorization = 'GREEN_CARD'
        candidate.location = 'New York, NY'
        candidate.primary_resume_id = None

        job = MagicMock(spec=JobPosting)
        job.title = 'Junior QA Engineer'
        job.company_name = 'StartUp'
        job.location = 'Remote Only'
        job.description = (
            'Entry level QA position. '
            'Requires 20+ years experience (wait, this is contradictory but testing the rule). '
            'Remote work possible but candidate is onsite-only.'
        )

        engine = FitScoringEngine()
        result = engine.calculate_fit_score(candidate, job)

        # Location blocker should be triggered
        assert result['hard_blockers']['location'] is True
        assert result['recommendation'] == 'skip'
        assert result['overall_score'] < 50

    def test_score_location_remote_match(self):
        """Test location scoring for remote preference match."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.remote_preference = 'REMOTE'

        job = MagicMock(spec=JobPosting)
        job.location = 'Remote'

        engine = FitScoringEngine()
        score = engine._score_location_match(candidate, job)
        assert score >= 95  # Perfect match

    def test_score_location_onsite_mismatch(self):
        """Test location scoring for onsite/remote mismatch."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.remote_preference = 'REMOTE'

        job = MagicMock(spec=JobPosting)
        job.location = 'San Francisco, CA'

        engine = FitScoringEngine()
        score = engine._score_location_match(candidate, job)
        assert score < 50  # Mismatch

    def test_score_seniority_mid_level_match(self):
        """Test seniority scoring for appropriate level match."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.years_experience = 5

        job = MagicMock(spec=JobPosting)
        job.description = 'Requires 5+ years of experience'

        engine = FitScoringEngine()
        score = engine._score_seniority_match(candidate, job)
        assert score >= 75  # Good match

    def test_score_seniority_underqualified(self):
        """Test seniority scoring when underqualified."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.years_experience = 2

        job = MagicMock(spec=JobPosting)
        job.description = 'Requires 10+ years of experience'

        engine = FitScoringEngine()
        score = engine._score_seniority_match(candidate, job)
        assert score < 70  # Poor match

    def test_score_work_auth_citizen(self):
        """Test work auth scoring for US citizen."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.work_authorization = 'US_CITIZEN'

        job = MagicMock(spec=JobPosting)
        job.description = ''

        engine = FitScoringEngine()
        score = engine._score_work_auth_match(candidate, job)
        assert score >= 95  # Perfect match

    def test_explanation_generation(self):
        """Test human-readable explanation generation."""
        candidate = MagicMock(spec=CandidateProfile)
        candidate.full_name = 'Test Candidate'
        candidate.target_titles = ['Data Scientist']
        candidate.years_experience = 4
        candidate.work_authorization = 'US_CITIZEN'
        candidate.salary_floor_usd = 100000
        candidate.remote_preference = 'HYBRID'
        candidate.location = 'SF Bay Area'
        candidate.primary_resume_id = None

        job = MagicMock(spec=JobPosting)
        job.title = 'Senior Data Scientist'
        job.company_name = 'DataCorp'
        job.location = 'San Francisco, CA'
        job.description = '5+ years experience, Python, ML, $150k-180k, Hybrid'

        engine = FitScoringEngine()
        result = engine.calculate_fit_score(candidate, job)

        explanation = result['explanation']
        assert explanation is not None
        assert len(explanation) > 0
        assert 'Match' in explanation or 'match' in explanation
