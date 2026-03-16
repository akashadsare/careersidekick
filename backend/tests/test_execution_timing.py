from datetime import UTC, datetime

from app.db_models import RunStatus, SubmissionRun
from app.routes.executions import _apply_status_timestamps


def test_apply_status_timestamps_sets_terminal_timing_fields() -> None:
    started = datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 3, 16, 12, 0, 5, tzinfo=UTC)
    run = SubmissionRun(run_status=RunStatus.RUNNING, started_at=started)

    _apply_status_timestamps(run, RunStatus.COMPLETED, now=finished)

    assert run.run_status == RunStatus.COMPLETED
    assert run.finished_at == finished
    assert run.duration_ms == 5000


def test_apply_status_timestamps_resets_terminal_fields_when_resuming() -> None:
    started = datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 3, 16, 12, 0, 5, tzinfo=UTC)
    resumed = datetime(2026, 3, 16, 12, 1, 0, tzinfo=UTC)
    run = SubmissionRun(
        run_status=RunStatus.FAILED,
        started_at=started,
        finished_at=finished,
        duration_ms=5000,
    )

    _apply_status_timestamps(run, RunStatus.RUNNING, now=resumed)

    assert run.run_status == RunStatus.RUNNING
    assert run.started_at == started
    assert run.finished_at is None
    assert run.duration_ms is None


def test_apply_status_timestamps_sets_started_at_when_missing() -> None:
    resumed = datetime(2026, 3, 16, 12, 1, 0, tzinfo=UTC)
    run = SubmissionRun(run_status=RunStatus.FAILED)

    _apply_status_timestamps(run, RunStatus.RUNNING, now=resumed)

    assert run.run_status == RunStatus.RUNNING
    assert run.started_at == resumed
    assert run.finished_at is None
    assert run.duration_ms is None
