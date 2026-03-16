from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.db_models import RunStatus, SubmissionRun
from app.models import SubmissionRunStatusUpdateRequest
from app.routes.executions import list_runs_page, update_run_status


class FakeQuery:
    def __init__(self, rows: list[SubmissionRun]):
        self._rows = rows
        self._limit: int | None = None

    def filter(self, _condition):
        return self

    def order_by(self, _clause):
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def all(self):
        if self._limit is None:
            return self._rows
        return self._rows[: self._limit]

    def count(self):
        return len(self._rows)


class FakeSession:
    def __init__(self, run: SubmissionRun | None = None, rows: list[SubmissionRun] | None = None):
        self._run = run
        self._rows = rows or []

    def get(self, _model, _run_id: int):
        return self._run

    def add(self, _obj):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def query(self, _model):
        return FakeQuery(self._rows)


def _make_run(run_id: int, status: RunStatus) -> SubmissionRun:
    t0 = datetime(2026, 3, 16, 8, 0, 0, tzinfo=UTC)
    return SubmissionRun(
        id=run_id,
        draft_id=7,
        tinyfish_run_id=f"tf-{run_id}",
        run_status=status,
        started_at=t0,
        finished_at=None,
        duration_ms=None,
        streaming_url=None,
        error_message=None,
        created_at=t0,
    )


def test_update_run_status_rejects_invalid_transition() -> None:
    run = _make_run(11, RunStatus.COMPLETED)
    db = FakeSession(run=run)

    with pytest.raises(HTTPException) as exc:
        update_run_status(11, SubmissionRunStatusUpdateRequest(run_status='running'), db)

    assert exc.value.status_code == 409
    assert 'invalid transition' in str(exc.value.detail)


def test_update_run_status_accepts_running_to_completed() -> None:
    run = _make_run(12, RunStatus.RUNNING)
    db = FakeSession(run=run)

    response = update_run_status(12, SubmissionRunStatusUpdateRequest(run_status='completed'), db)

    assert response.id == 12
    assert response.run_status == 'completed'
    assert run.finished_at is not None
    assert run.duration_ms is not None
    assert run.duration_ms >= 0


def test_list_runs_page_includes_total_count_and_cursor_metadata() -> None:
    rows = [
        _make_run(30, RunStatus.RUNNING),
        _make_run(29, RunStatus.COMPLETED),
        _make_run(28, RunStatus.FAILED),
    ]
    db = FakeSession(rows=rows)

    response = list_runs_page(status=None, draft_id=None, limit=2, cursor=None, sort_direction='desc', db=db)

    assert len(response.data) == 2
    assert response.pagination.total_count == 3
    assert response.pagination.has_more is True
    assert response.pagination.next_cursor == 29


def test_list_runs_page_rejects_invalid_sort_direction() -> None:
    db = FakeSession(rows=[])

    with pytest.raises(HTTPException) as exc:
        list_runs_page(status=None, draft_id=None, limit=10, cursor=None, sort_direction='sideways', db=db)

    assert exc.value.status_code == 400
