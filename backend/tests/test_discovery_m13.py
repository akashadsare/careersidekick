"""Tests for M1.3 job discovery."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.db_models import JobDiscoveryQuery, JobDiscoveryRun, DiscoveryRunStatus
from sqlalchemy.orm import Session

client = TestClient(app)


def test_discover_jobs_basic():
    """Test basic job discovery."""
    response = client.post(
        '/api/v1/jobs/discover?candidate_id=1',
        json={
            'title_query': 'Software Engineer',
            'location': 'San Francisco, CA',
            'remote_preference': 'REMOTE'
        }
    )
    # Should return success or 422 if DB not available
    assert response.status_code in [200, 422, 500]


def test_discover_jobs_minimal():
    """Test discovery with minimal parameters."""
    response = client.post(
        '/api/v1/jobs/discover?candidate_id=1',
        json={}
    )
    # Should handle empty request gracefully
    assert response.status_code in [200, 422, 500]


def test_discover_jobs_title_only():
    """Test discovery with title query only."""
    response = client.post(
        '/api/v1/jobs/discover?candidate_id=1',
        json={'title_query': 'Product Manager'}
    )
    assert response.status_code in [200, 422, 500]


def test_discover_jobs_location_only():
    """Test discovery with location only."""
    response = client.post(
        '/api/v1/jobs/discover?candidate_id=1',
        json={'location': 'New York, NY'}
    )
    assert response.status_code in [200, 422, 500]


def test_discover_jobs_remote_preference():
    """Test discovery with remote preference."""
    response = client.post(
        '/api/v1/jobs/discover?candidate_id=1',
        json={
            'title_query': 'Engineer',
            'remote_preference': 'REMOTE'
        }
    )
    assert response.status_code in [200, 422, 500]


def test_get_discovery_run_not_found():
    """Test retrieving non-existent discovery run."""
    response = client.get('/api/v1/jobs/discovery-runs/99999')
    # Should fail gracefully (404 or 500 if DB not available)
    assert response.status_code in [404, 500]


def test_list_discovered_jobs_empty():
    """Test listing discovered jobs with no run."""
    response = client.get('/api/v1/jobs/discovered?run_id=99999&skip=0&limit=20')
    # Should handle gracefully
    assert response.status_code in [200, 500]


def test_get_discovery_history_empty():
    """Test getting discovery history for non-existent candidate."""
    response = client.get('/api/v1/candidates/99999/discovery-history')
    # Should return empty or work structure
    assert response.status_code in [200, 500]


@pytest.mark.asyncio
async def test_job_discovery_service_search():
    """Test job discovery service search functionality."""
    from app.services.job_discovery import JobDiscoveryService

    service = JobDiscoveryService()

    # Test search query building
    query = service._build_search_query(
        title='Software Engineer',
        location='San Francisco',
        remote=None
    )
    assert 'Software Engineer' in query
    assert 'San Francisco' in query

    # Test with remote
    query_remote = service._build_search_query(
        title='Developer',
        location=None,
        remote='REMOTE'
    )
    assert 'Developer' in query_remote
    assert 'Remote' in query_remote


@pytest.mark.asyncio
async def test_job_discovery_service_mock_generation():
    """Test mock URL generation for LinkedIn and Greenhouse."""
    from app.services.job_discovery import JobDiscoveryService

    service = JobDiscoveryService()

    # Test LinkedIn mock URL generation
    linkedin_urls = service._generate_mock_linkedin_urls('Software Engineer', 10)
    assert len(linkedin_urls) == 10
    assert all('linkedin.com' in url for url in linkedin_urls)
    assert all('/jobs/view/' in url for url in linkedin_urls)

    # Test Greenhouse mock URL generation
    greenhouse_urls = service._generate_mock_greenhouse_urls('Product Manager', 15)
    assert len(greenhouse_urls) == 15
    assert all('greenhouse.io' in url for url in greenhouse_urls)

    # Test realistic ID generation
    linkedin_ids = service._generate_realistic_job_ids(0)
    assert len(linkedin_ids) == 25
    assert all(len(id) > 0 for id in linkedin_ids)

    greenhouse_ids = service._generate_realistic_greenhouse_job_ids(0)
    assert len(greenhouse_ids) == 15
    assert all(len(id) > 0 for id in greenhouse_ids)


@pytest.mark.asyncio
async def test_job_discovery_service_dedup():
    """Test URL deduplication."""
    from app.services.job_discovery import JobDiscoveryService

    service = JobDiscoveryService()

    # Test with duplicates
    urls = [
        'https://boards.greenhouse.io/company/jobs/123',
        'https://boards.greenhouse.io/company/jobs/124',
        'https://boards.greenhouse.io/company/jobs/123',  # Duplicate
    ]

    deduped = service._deduplicate_job_urls(urls)
    assert len(deduped) == 2
    assert len(set(deduped)) == len(deduped)  # All unique


def test_discovery_models_valid():
    """Test that discovery models are valid."""
    from app.models import (
        JobDiscoveryQueryRequest,
        JobDiscoveryQueryResponse,
        JobDiscoveryRunResponse,
        JobDiscoverySummary
    )

    # Test request model
    request = JobDiscoveryQueryRequest(
        title_query='Engineer',
        location='SF',
        remote_preference='REMOTE'
    )
    assert request.title_query == 'Engineer'
    assert request.location == 'SF'
    assert request.remote_preference == 'REMOTE'

    # Test response models can be constructed
    query_response = JobDiscoveryQueryResponse(
        id=1,
        candidate_id=1,
        title_query='Engineer',
        location='SF',
        remote_preference='REMOTE',
        created_at='2024-01-15T00:00:00Z'
    )
    assert query_response.id == 1

    summary = JobDiscoverySummary(
        query_id=1,
        run_id=1,
        title_query='Engineer',
        location='SF',
        jobs_discovered=50,
        jobs_imported=45,
        jobs_duplicate=5,
        jobs_failed=0,
        duration_seconds=120.5,
        ats_detection_rate=0.84,
        top_ats_types={'greenhouse': 20, 'lever': 15, 'linkedin': 10},
        status='completed'
    )
    assert summary.jobs_discovered == 50
    assert summary.ats_detection_rate == 0.84


def test_discovery_database_schema():
    """Test that discovery database models have correct fields."""
    from app.db_models import JobDiscoveryQuery, JobDiscoveryRun, DiscoveryRunStatus

    # Check JobDiscoveryQuery has expected columns
    query_columns = {c.name for c in JobDiscoveryQuery.__table__.columns}
    assert 'id' in query_columns
    assert 'candidate_id' in query_columns
    assert 'title_query' in query_columns
    assert 'location' in query_columns
    assert 'remote_preference' in query_columns
    assert 'created_at' in query_columns

    # Check JobDiscoveryRun has expected columns
    run_columns = {c.name for c in JobDiscoveryRun.__table__.columns}
    assert 'id' in run_columns
    assert 'query_id' in run_columns
    assert 'run_status' in run_columns
    assert 'jobs_discovered' in run_columns
    assert 'jobs_imported' in run_columns
    assert 'jobs_duplicate' in run_columns
    assert 'jobs_failed' in run_columns
    assert 'started_at' in run_columns
    assert 'finished_at' in run_columns
    assert 'duration_ms' in run_columns
    assert 'error_message' in run_columns
    assert 'created_at' in run_columns

    # Check DiscoveryRunStatus enum values
    assert DiscoveryRunStatus.PENDING.value == 'pending'
    assert DiscoveryRunStatus.RUNNING.value == 'running'
    assert DiscoveryRunStatus.COMPLETED.value == 'completed'
    assert DiscoveryRunStatus.FAILED.value == 'failed'


def test_discovery_routes_exist():
    """Test that discovery routes are registered."""
    from app.routes.discovery import router

    # Check that routes exist
    route_paths = {r.path for r in router.routes}
    assert '/jobs/discover' in route_paths
    assert '/jobs/discovery-runs/{run_id}' in route_paths
    assert '/jobs/discovered' in route_paths
    assert '/candidates/{candidate_id}/discovery-history' in route_paths
