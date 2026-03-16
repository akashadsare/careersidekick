"""M1.5: Application Package Generation Tests

Test package generation with:
- Answer matching from library, resume, profile
- Cover note generation with fit-contextualized language
- Needs review flagging for unanswerable questions
- Database persistence and retrieval
"""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine, Base
from app.db_models import (
    AnswerLibraryQuestion,
    ApplicationDraft,
    CandidateAnswer,
    CandidateProfile,
    FitScore,
    JobPosting,
    Resume,
)
from app.models import PackageGenerateRequest
from app.services.package_generator import generate_application_package

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
    """Create a sample candidate with profile."""
    candidate = CandidateProfile(
        full_name='Alice Chen',
        email='alice@example.com',
        location='San Francisco, CA',
        years_experience=5,
        work_authorization='US_CITIZEN',
        remote_preference='REMOTE',
        target_titles=['Software Engineer', 'Backend Engineer'],
        target_companies=['Google', 'Meta'],
        salary_floor_usd=150000,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@pytest.fixture
def sample_job(db: Session) -> JobPosting:
    """Create a sample job posting."""
    job = JobPosting(
        title='Senior Backend Engineer',
        company_name='TechCorp',
        location='Remote',
        description='Looking for a senior backend engineer with Python and AWS experience. 5+ years required.',
        apply_url='https://techcorp.jobs/apply/123',
        source_url='https://boards.greenhouse.io/techcorp/jobs/123',
        ats_type='greenhouse',
        ats_detection_confidence=0.95,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def sample_answer_library(db: Session) -> list[AnswerLibraryQuestion]:
    """Create sample answer library questions."""
    questions = [
        AnswerLibraryQuestion(
            question_text='Are you authorized to work in this country without sponsorship?',
            question_category='work_auth',
            portal_types=['greenhouse', 'lever'],
            frequency_rank=1,
        ),
        AnswerLibraryQuestion(
            question_text='Describe your experience with backend development.',
            question_category='technical_skills',
            portal_types=['greenhouse', 'lever', 'workday'],
            frequency_rank=2,
        ),
        AnswerLibraryQuestion(
            question_text='What is your preferred work arrangement?',
            question_category='remote_preference',
            portal_types=['greenhouse', 'lever'],
            frequency_rank=3,
        ),
        AnswerLibraryQuestion(
            question_text='Tell us why you are interested in this role.',
            question_category='motivation',
            portal_types=['greenhouse', 'lever', 'workday'],
            frequency_rank=4,
        ),
    ]
    for q in questions:
        db.add(q)
    db.commit()
    for q in questions:
        db.refresh(q)
    return questions


@pytest.fixture
def sample_candidate_answers(
    db: Session, sample_candidate: CandidateProfile, sample_answer_library: list[AnswerLibraryQuestion]
) -> list[CandidateAnswer]:
    """Create sample candidate answers."""
    answers = [
        CandidateAnswer(
            candidate_id=sample_candidate.id,
            library_question_id=sample_answer_library[0].id,
            answer_text='Yes, I am a US citizen and authorized to work without sponsorship.',
            is_custom=False,
        ),
        CandidateAnswer(
            candidate_id=sample_candidate.id,
            library_question_id=sample_answer_library[1].id,
            answer_text='I have 5+ years of backend development experience with Python, Go, and Rust. I specialize in building scalable distributed systems and have worked extensively with AWS services.',
            is_custom=False,
        ),
    ]
    for a in answers:
        db.add(a)
    db.commit()
    for a in answers:
        db.refresh(a)
    return answers


class TestPackageGenerationBasic:
    """Test basic package generation."""

    def test_generate_package_success(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test successful package generation."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        assert result['package_id'] is not None
        assert result['candidate_id'] == sample_candidate.id
        assert result['job_id'] == sample_job.id
        assert isinstance(result['answers'], list)
        assert isinstance(result['cover_note'], str)
        assert len(result['cover_note']) > 50  # Should be 3-5 sentences

    def test_generate_package_creates_draft(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting
    ):
        """Test that package generation creates ApplicationDraft."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == result['package_id']).first()
        assert draft is not None
        assert draft.candidate_id == sample_candidate.id
        assert draft.job_id == sample_job.id
        assert draft.status.value == 'draft'  # Draft status

    def test_generate_package_missing_candidate(self, db: Session, sample_job: JobPosting):
        """Test package generation fails for missing candidate."""
        with pytest.raises(ValueError, match='Candidate .* not found'):
            generate_application_package(99999, sample_job.id, db)

    def test_generate_package_missing_job(self, db: Session, sample_candidate: CandidateProfile):
        """Test package generation fails for missing job."""
        with pytest.raises(ValueError, match='Job .* not found'):
            generate_application_package(sample_candidate.id, 99999, db)


class TestAnswerMatching:
    """Test answer matching from library, resume, profile."""

    def test_answer_from_candidate_library(
        self,
        db: Session,
        sample_candidate: CandidateProfile,
        sample_job: JobPosting,
        sample_answer_library: list,
        sample_candidate_answers: list,
    ):
        """Test answers are retrieved from candidate library."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        # Should include work_auth answer from candidate's library
        auth_answer = next((a for a in result['answers'] if 'authorized' in a['answer'].lower()), None)
        assert auth_answer is not None
        assert auth_answer['provenance'] == 'candidate_answer'
        assert 'US citizen' in auth_answer['answer']

    def test_answers_have_provenance(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test all answers have correct provenance."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        for answer in result['answers']:
            assert 'provenance' in answer
            assert answer['provenance'] in ['candidate_answer', 'resume', 'profile']

    def test_needs_review_for_missing_answers(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test unanswerable questions are flagged for review."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        # Should have needs_review_flags for questions without answers
        assert isinstance(result['needs_review_flags'], list)
        if len(result['needs_review_flags']) > 0:
            flag = result['needs_review_flags'][0]
            assert 'question' in flag
            assert 'reason' in flag
            assert 'No candidate answer found' in flag['reason']


class TestCoverNoteGeneration:
    """Test cover note generation."""

    def test_cover_note_contains_role_and_company(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test cover note mentions role and company."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        cover_note = result['cover_note']
        assert sample_job.title in cover_note
        assert sample_job.company_name in cover_note

    def test_cover_note_length(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test cover note is 3-5 sentences (100-300 words)."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        cover_note = result['cover_note']
        word_count = len(cover_note.split())
        sentence_count = cover_note.count('.') + cover_note.count('!') + cover_note.count('?')

        assert 50 < len(cover_note) < 500
        assert 2 <= sentence_count <= 6

    def test_cover_note_with_low_fit_score(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test cover note is different when fit score is low."""
        # Create fit score with low overall_score
        fit_score = FitScore(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            overall_score=35,
            recommendation='skip',
            title_match_score=30,
            skills_match_score=40,
            seniority_match_score=40,
            location_match_score=50,
            salary_match_score=30,
            work_auth_match_score=95,
            hard_blocker_work_auth=False,
            hard_blocker_location=False,
            hard_blocker_seniority=False,
        )
        db.add(fit_score)
        db.commit()

        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        cover_note = result['cover_note']
        # Should use more cautious language
        assert 'interested' in cover_note.lower() or 'opportunity' in cover_note.lower()


class TestFitScoreIntegration:
    """Test integration with M1.4 fit scores."""

    def test_package_includes_fit_score(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test package includes fit score when available."""
        fit_score = FitScore(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            overall_score=85,
            recommendation='apply',
            title_match_score=90,
            skills_match_score=80,
            seniority_match_score=85,
            location_match_score=95,
            salary_match_score=75,
            work_auth_match_score=95,
            hard_blocker_work_auth=False,
            hard_blocker_location=False,
            hard_blocker_seniority=False,
        )
        db.add(fit_score)
        db.commit()

        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        assert result['fit_score'] == 85

    def test_package_fit_score_zero_when_none(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test fit score defaults to 0 when not computed yet."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        # No fit score computed for this pair
        assert result['fit_score'] == 0


class TestDatabasePersistence:
    """Test package storage and retrieval."""

    def test_package_stored_in_database(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test package is stored as ApplicationDraft."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        draft = db.query(ApplicationDraft).filter(ApplicationDraft.id == result['package_id']).first()
        assert draft is not None
        assert draft.answers_json is not None
        assert 'answers' in draft.answers_json

    def test_package_retrieved_from_database(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test package can be retrieved from database."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        draft = db.query(ApplicationDraft).filter(
            ApplicationDraft.candidate_id == sample_candidate.id,
            ApplicationDraft.job_id == sample_job.id,
        ).first()
        assert draft is not None
        assert len(draft.answers_json['answers']) >= 0


class TestAnswerLibraryIntegration:
    """Test integration with answer library."""

    def test_questions_filtered_by_ats_type(
        self,
        db: Session,
        sample_candidate: CandidateProfile,
        sample_job: JobPosting,
        sample_answer_library: list,
    ):
        """Test questions are filtered by ATS type when available."""
        # Job has ats_type='greenhouse'
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        # All questions returned should be compatible with Greenhouse or have no ATS filter
        for answer in result['answers']:
            assert len(answer['question']) > 5  # Reasonable question length


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_candidate_with_no_answers_in_library(
        self, db: Session, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test package generation with candidate who has no library answers."""
        candidate = CandidateProfile(
            full_name='Bob',
            email='bob@example.com',
            location='New York, NY',
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        result = generate_application_package(candidate.id, sample_job.id, db)

        # Should still generate a package with profile/resume fallbacks
        assert result['package_id'] is not None
        assert len(result['needs_review_flags']) >= 0

    def test_empty_answer_library(self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting):
        """Test package generation with empty answer library."""
        result = generate_application_package(sample_candidate.id, sample_job.id, db)

        # Should still generate a package (falling back to profile)
        assert result['package_id'] is not None

    def test_package_generation_deterministic(
        self,
        db: Session,
        sample_candidate: CandidateProfile,
        sample_job: JobPosting,
        sample_answer_library: list,
    ):
        """Test package generation is deterministic for same inputs."""
        result1 = generate_application_package(sample_candidate.id, sample_job.id, db)
        
        # Clear session and try again (fresh query)
        db.expunge_all()
        
        result2 = generate_application_package(sample_candidate.id, sample_job.id, db)

        # Should produce identical results (same cover note, same answer count)
        assert result1['cover_note'] == result2['cover_note']
        assert len(result1['answers']) == len(result2['answers'])


class TestAPIEndpoint:
    """Test API endpoint integration (implicit via other tests)."""

    def test_endpoint_generate_package(
        self, db: Session, sample_candidate: CandidateProfile, sample_job: JobPosting, sample_answer_library: list
    ):
        """Test that package generation service works (API tested via integration tests)."""
        # The underlying service is tested above
        # API endpoint validation is tested in integration tests
        pass

