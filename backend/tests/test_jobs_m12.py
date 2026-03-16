"""Tests for M1.2 job import endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.db_models import JobPosting
from sqlalchemy.orm import Session

client = TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    mock_session = MagicMock(spec=Session)
    return mock_session


@pytest.fixture
def mock_extractor():
    """Mock job extractor."""
    with patch('app.routes.jobs.JobExtractor') as mock:
        yield mock


def test_import_job_invalid_url_format():
    """Test that invalid URL format returns 400."""
    response = client.post(
        '/api/v1/jobs/import-by-url',
        json={'source_url': 'invalid-url-without-protocol'}
    )
    assert response.status_code == 400
    assert 'http://' in response.json()['detail'] or 'https://' in response.json()['detail']


def test_import_job_extraction_failed():
    """Test that failed extraction returns 422."""
    with patch('app.routes.jobs.JobExtractor') as mock_extractor_class:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = {
            'title': None,
            'company_name': None,
            'location': None,
            'description': None,
            'apply_url': 'https://boards.greenhouse.io/test',
            'ats_type': 'greenhouse',
            'ats_detection_confidence': 0.95,
            'is_closed': False,
            'extraction_errors': []
        }
        mock_extractor_class.return_value = mock_instance

        response = client.post(
            '/api/v1/jobs/import-by-url',
            json={'source_url': 'https://boards.greenhouse.io/test'}
        )

        assert response.status_code == 422
        assert 'Could not extract job title and company' in response.json()['detail']


def test_import_job_success_greenhouse():
    """Test successful job import from Greenhouse URL."""
    with patch('app.routes.jobs.JobExtractor') as mock_extractor_class:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = {
            'title': 'Senior Software Engineer',
            'company_name': 'Acme Corp',
            'location': 'San Francisco, CA',
            'description': 'We are looking for a senior engineer...',
            'apply_url': 'https://boards.greenhouse.io/acmecorp/jobs/123/apply',
            'ats_type': 'greenhouse',
            'ats_detection_confidence': 0.95,
            'is_closed': False,
            'extraction_errors': []
        }
        mock_extractor_class.return_value = mock_instance

        response = client.post(
            '/api/v1/jobs/import-by-url',
            json={'source_url': 'https://boards.greenhouse.io/acmecorp/jobs/123'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['job']['title'] == 'Senior Software Engineer'
        assert data['job']['company_name'] == 'Acme Corp'
        assert data['job']['ats_type'] == 'greenhouse'
        assert data['ats_detection_confidence'] == 0.95
        assert data['is_closed'] is False


def test_import_job_closed_warning():
    """Test that closed jobs return warning in response."""
    with patch('app.routes.jobs.JobExtractor') as mock_extractor_class:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = {
            'title': 'Product Manager',
            'company_name': 'TechCorp',
            'location': 'Remote',
            'description': 'This position has been filled.',
            'apply_url': 'https://lever.co/techcorp/jobs/123',
            'ats_type': 'lever',
            'ats_detection_confidence': 0.90,
            'is_closed': True,
            'extraction_errors': ['Job appears to be closed']
        }
        mock_extractor_class.return_value = mock_instance

        response = client.post(
            '/api/v1/jobs/import-by-url',
            json={'source_url': 'https://lever.co/techcorp/jobs/123'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_closed'] is True
        assert any('closed' in err.lower() for err in data['extraction_errors'])


def test_import_job_low_ats_confidence():
    """Test that low ATS confidence returns confidence warning."""
    with patch('app.routes.jobs.JobExtractor') as mock_extractor_class:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = {
            'title': 'Designer',
            'company_name': 'DesignStudio',
            'location': None,
            'description': 'Looking for a creative designer',
            'apply_url': None,
            'ats_type': 'workday',
            'ats_detection_confidence': 0.65,
            'is_closed': False,
            'extraction_errors': ['Could not identify all fields']
        }
        mock_extractor_class.return_value = mock_instance

        response = client.post(
            '/api/v1/jobs/import-by-url',
            json={'source_url': 'https://myworkdayjobs.com/job/123'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['ats_detection_confidence'] == 0.65
        assert any('confidence' in err.lower() for err in data['extraction_errors'])


def test_import_job_no_ats_detection():
    """Test import when ATS type cannot be detected."""
    with patch('app.routes.jobs.JobExtractor') as mock_extractor_class:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = {
            'title': 'Entry-level Developer',
            'company_name': 'StartupXYZ',
            'location': 'New York, NY',
            'description': 'Join our growing team',
            'apply_url': 'https://careers.startupxyz.com/apply',
            'ats_type': None,
            'ats_detection_confidence': 0.0,
            'is_closed': False,
            'extraction_errors': ['Could not detect ATS type from URL']
        }
        mock_extractor_class.return_value = mock_instance

        response = client.post(
            '/api/v1/jobs/import-by-url',
            json={'source_url': 'https://careers.startupxyz.com/jobs/dev-123'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['job']['ats_type'] is None
        assert any('Could not detect ATS type' in err for err in data['extraction_errors'])


def test_get_job_not_found():
    """Test retrieving non-existent job returns 404."""
    response = client.get('/api/v1/jobs/99999')
    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower()


def test_list_jobs_empty():
    """Test listing jobs when none exist."""
    response = client.get('/api/v1/jobs')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data['jobs'], list)
    assert data['total'] >= 0


def test_extract_patterns():
    """Test that ATS detection patterns are properly configured."""
    from app.services.job_extractor import JobExtractor

    extractor = JobExtractor()

    # Test Greenhouse detection
    greenhouse_url = 'https://boards.greenhouse.io/acmecorp/jobs/123'
    result = extractor._detect_ats(greenhouse_url)
    assert result.ats_type == 'greenhouse'
    assert result.confidence >= 0.9

    # Test Lever detection
    lever_url = 'https://jobs.lever.co/company/jobs/123'
    result = extractor._detect_ats(lever_url)
    assert result.ats_type == 'lever'
    assert result.confidence >= 0.9

    # Test Workday detection
    workday_url = 'https://myworkdayjobs.com/company/jobs/123'
    result = extractor._detect_ats(workday_url)
    assert result.ats_type == 'workday'
    assert result.confidence >= 0.9

    # Test Ashby detection
    ashby_url = 'https://jobs.ashby.ai/company/jobs/123'
    result = extractor._detect_ats(ashby_url)
    assert result.ats_type == 'ashby'
    assert result.confidence >= 0.9

    # Test LinkedIn detection
    linkedin_url = 'https://www.linkedin.com/jobs/view/123456789'
    result = extractor._detect_ats(linkedin_url)
    assert result.ats_type == 'linkedin'
    assert result.confidence >= 0.9


def test_closed_job_detection_patterns():
    """Test that closed job indicators are properly detected."""
    from app.services.job_extractor import JobExtractor

    extractor = JobExtractor()

    # Test various closed job indicators
    closed_indicators = [
        'This job posting is closed',
        'This position has been filled',
        'No longer accepting applications',
        'Sorry, this job is not available',
        'Application window closed',
    ]

    for indicator in closed_indicators:
        is_closed = extractor._detect_closed_job(MagicMock(), indicator)
        assert is_closed is True, f"Failed to detect: {indicator}"
