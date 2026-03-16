import asyncio
from datetime import UTC, datetime
from typing import Any

from app.db_models import RunStatus, SubmissionRun
from app.models import TinyFishRunRequest
from app.routes import executions


class FakeSession:
    def __init__(self) -> None:
        self.last_run: SubmissionRun | None = None
        self.commits = 0

    def add(self, obj: SubmissionRun) -> None:
        self.last_run = obj

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj: SubmissionRun) -> None:
        if obj.id is None:
            obj.id = 1
        if obj.created_at is None:
            obj.created_at = datetime.now(UTC)


async def _collect_stream_lines(response: Any) -> list[str]:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return chunks


def test_run_sse_updates_run_on_completed_events(monkeypatch) -> None:
    async def fake_stream(_payload: dict[str, object]):
        yield 'data: {"type":"STARTED","runId":"tf-123"}\n'
        yield 'data: {"type":"STREAMING_URL","streamingUrl":"https://stream.local/1"}\n'
        yield (
            'data: {"type":"COMPLETE","status":"COMPLETED",'
            '"resultJson":{"products":[{"name":"A"}]}}\n'
        )

    monkeypatch.setattr(executions, 'stream_tinyfish_sse', fake_stream)

    req = TinyFishRunRequest(url='https://scrapeme.live/shop', goal='extract first product')
    db = FakeSession()

    response = asyncio.run(executions.run_sse(req, db))
    lines = asyncio.run(_collect_stream_lines(response))

    assert response.headers.get('X-Execution-Id') == '1'
    assert any('STARTED' in line for line in lines)
    assert any('STREAMING_URL' in line for line in lines)
    assert any('COMPLETE' in line for line in lines)

    assert db.last_run is not None
    assert db.last_run.tinyfish_run_id == 'tf-123'
    assert db.last_run.streaming_url == 'https://stream.local/1'
    assert db.last_run.run_status == RunStatus.COMPLETED
    assert db.last_run.duration_ms is not None
    assert db.last_run.result_json == {'products': [{'name': 'A'}]}


def test_run_sse_updates_run_on_failed_complete_event(monkeypatch) -> None:
    async def fake_stream(_payload: dict[str, object]):
        yield (
            'data: {"type":"COMPLETE","status":"FAILED",'
            '"error":{"message":"blocked by site"}}\n'
        )

    monkeypatch.setattr(executions, 'stream_tinyfish_sse', fake_stream)

    req = TinyFishRunRequest(url='https://example.com/apply', goal='submit form')
    db = FakeSession()

    response = asyncio.run(executions.run_sse(req, db))
    lines = asyncio.run(_collect_stream_lines(response))

    assert response.headers.get('X-Execution-Id') == '1'
    assert any('COMPLETE' in line for line in lines)

    assert db.last_run is not None
    assert db.last_run.run_status == RunStatus.FAILED
    assert db.last_run.error_message == 'blocked by site'
    assert db.last_run.finished_at is not None


def test_run_sse_ignores_invalid_data_chunk_and_continues(monkeypatch) -> None:
    async def fake_stream(_payload: dict[str, object]):
        yield 'data: {not-json}\n'
        yield 'event: keep-alive\n'
        yield 'data: {"type":"STARTED","runId":"tf-777"}\n'

    monkeypatch.setattr(executions, 'stream_tinyfish_sse', fake_stream)

    req = TinyFishRunRequest(url='https://example.com', goal='smoke')
    db = FakeSession()

    response = asyncio.run(executions.run_sse(req, db))
    lines = asyncio.run(_collect_stream_lines(response))

    assert any('{not-json}' in line for line in lines)
    assert any('event: keep-alive' in line for line in lines)
    assert db.last_run is not None
    assert db.last_run.tinyfish_run_id == 'tf-777'
    assert db.last_run.run_status == RunStatus.RUNNING
