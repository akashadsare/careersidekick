from datetime import UTC, datetime

from app.db_models import RunStatus, SubmissionRun
from app.routes.executions import _compute_execution_metrics, get_execution_metrics


class FakeQuery:
    def __init__(self, rows: list[SubmissionRun]):
        self._rows = rows

    def filter(self, _condition):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows: list[SubmissionRun]):
        self._rows = rows

    def query(self, _model):
        return FakeQuery(self._rows)


def _make_run(run_id: int, status: RunStatus, created_at: datetime, duration_ms: int | None) -> SubmissionRun:
    return SubmissionRun(
        id=run_id,
        draft_id=1,
        tinyfish_run_id=f'tf-{run_id}',
        run_status=status,
        started_at=created_at,
        finished_at=created_at,
        duration_ms=duration_ms,
        streaming_url=None,
        error_message=None,
        created_at=created_at,
    )


def test_compute_execution_metrics_aggregates_counts_and_failure_buckets() -> None:
    rows = [
        _make_run(1, RunStatus.COMPLETED, datetime(2026, 3, 15, 8, 0, tzinfo=UTC), 1000),
        _make_run(2, RunStatus.COMPLETED, datetime(2026, 3, 15, 9, 0, tzinfo=UTC), 3000),
        _make_run(3, RunStatus.FAILED, datetime(2026, 3, 16, 10, 0, tzinfo=UTC), None),
        _make_run(4, RunStatus.FAILED, datetime(2026, 3, 16, 11, 0, tzinfo=UTC), None),
        _make_run(5, RunStatus.CANCELLED, datetime(2026, 3, 16, 12, 0, tzinfo=UTC), None),
        _make_run(6, RunStatus.RUNNING, datetime(2026, 3, 16, 13, 0, tzinfo=UTC), None),
    ]

    metrics = _compute_execution_metrics(rows, window_days=30)

    assert metrics.window_days == 30
    assert metrics.total_runs == 6
    assert metrics.completed_runs == 2
    assert metrics.failed_runs == 2
    assert metrics.cancelled_runs == 1
    assert metrics.running_runs == 1
    assert metrics.success_rate == 33.33
    assert metrics.avg_duration_ms == 2000
    assert len(metrics.failures_by_day) == 1
    assert metrics.failures_by_day[0].day == '2026-03-16'
    assert metrics.failures_by_day[0].count == 2


def test_compute_execution_metrics_handles_empty_rows() -> None:
    metrics = _compute_execution_metrics([], window_days=7)

    assert metrics.window_days == 7
    assert metrics.total_runs == 0
    assert metrics.success_rate == 0.0
    assert metrics.avg_duration_ms is None
    assert metrics.failures_by_day == []


def test_get_execution_metrics_returns_response_model() -> None:
    rows = [
        _make_run(10, RunStatus.COMPLETED, datetime(2026, 3, 16, 8, 0, tzinfo=UTC), 1200),
        _make_run(11, RunStatus.FAILED, datetime(2026, 3, 16, 9, 0, tzinfo=UTC), None),
    ]
    db = FakeSession(rows)

    response = get_execution_metrics(days=30, db=db)

    assert response.window_days == 30
    assert response.total_runs == 2
    assert response.completed_runs == 1
    assert response.failed_runs == 1
