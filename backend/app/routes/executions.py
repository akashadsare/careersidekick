import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from ..db import get_db
from ..db_models import AlertIncident, IncidentState, RunStatus, SubmissionRun
from ..models import (
    DailyFailureCount,
    ExecutionHistoryPagination,
    ExecutionHistoryResponse,
    ExecutionMetricsResponse,
    IncidentEventCreateRequest,
    IncidentEventResponse,
    SubmissionRunDetailResponse,
    SubmissionRunResponse,
    SubmissionRunStatusUpdateRequest,
    SubmissionRunStatusUpdateResponse,
    TinyFishRunRequest,
)
from ..services.tinyfish_client import stream_tinyfish_sse

router = APIRouter()

TERMINAL_RUN_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


def _incident_response(row: AlertIncident) -> IncidentEventResponse:
    return IncidentEventResponse(
        id=row.id,
        state=row.state.value,
        message=row.message,
        created_at=row.created_at,
    )


def _apply_status_timestamps(run: SubmissionRun, target: RunStatus, now: datetime | None = None) -> None:
    current_time = now or datetime.now(UTC)
    run.run_status = target

    if target == RunStatus.RUNNING:
        if run.started_at is None:
            run.started_at = current_time
        # A resumed run should not carry terminal timestamps from a previous attempt.
        run.finished_at = None
        run.duration_ms = None
        return

    if target in TERMINAL_RUN_STATUSES:
        if run.finished_at is None:
            run.finished_at = current_time
        if run.started_at is not None:
            delta_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            run.duration_ms = max(delta_ms, 0)


@router.get('', response_model=list[SubmissionRunResponse])
def list_runs(
    status: str | None = Query(default=None),
    draft_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SubmissionRunResponse]:
    query = db.query(SubmissionRun)

    if status:
        try:
            query = query.filter(SubmissionRun.run_status == RunStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='invalid status filter') from exc

    if draft_id is not None:
        query = query.filter(SubmissionRun.draft_id == draft_id)

    rows = query.order_by(SubmissionRun.id.desc()).offset(offset).limit(limit).all()
    return [
        SubmissionRunResponse(
            id=row.id,
            draft_id=row.draft_id,
            tinyfish_run_id=row.tinyfish_run_id,
            run_status=row.run_status.value,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            streaming_url=row.streaming_url,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get('/page', response_model=ExecutionHistoryResponse)
def list_runs_page(
    status: str | None = Query(default=None),
    draft_id: int | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    cursor: int | None = Query(default=None),
    sort_direction: str = Query(default='desc'),
    db: Session = Depends(get_db),
) -> ExecutionHistoryResponse:
    if sort_direction not in ('asc', 'desc'):
        raise HTTPException(status_code=400, detail='invalid sort_direction; use asc or desc')

    query = db.query(SubmissionRun)

    if status:
        try:
            query = query.filter(SubmissionRun.run_status == RunStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='invalid status filter') from exc

    if draft_id is not None:
        query = query.filter(SubmissionRun.draft_id == draft_id)

    total_count = query.count()

    if cursor is not None:
        if sort_direction == 'desc':
            query = query.filter(SubmissionRun.id < cursor)
        else:
            query = query.filter(SubmissionRun.id > cursor)

    order_clause = SubmissionRun.id.desc() if sort_direction == 'desc' else SubmissionRun.id.asc()
    rows = query.order_by(order_clause).limit(limit + 1).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = page_rows[-1].id if has_more and page_rows else None

    data = [
        SubmissionRunResponse(
            id=row.id,
            draft_id=row.draft_id,
            tinyfish_run_id=row.tinyfish_run_id,
            run_status=row.run_status.value,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            streaming_url=row.streaming_url,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in page_rows
    ]

    return ExecutionHistoryResponse(
        data=data,
        pagination=ExecutionHistoryPagination(
            limit=limit,
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
            sort_direction='asc' if sort_direction == 'asc' else 'desc',
        ),
    )


def _compute_execution_metrics(rows: list[SubmissionRun], window_days: int) -> ExecutionMetricsResponse:
    total_runs = len(rows)
    completed_runs = sum(1 for row in rows if row.run_status == RunStatus.COMPLETED)
    failed_runs = sum(1 for row in rows if row.run_status == RunStatus.FAILED)
    cancelled_runs = sum(1 for row in rows if row.run_status == RunStatus.CANCELLED)
    running_runs = sum(1 for row in rows if row.run_status == RunStatus.RUNNING)

    success_rate = round((completed_runs / total_runs) * 100, 2) if total_runs else 0.0

    durations = [row.duration_ms for row in rows if row.duration_ms is not None]
    avg_duration_ms = int(sum(durations) / len(durations)) if durations else None

    failures_by_day_map: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.run_status == RunStatus.FAILED and row.created_at is not None:
            failures_by_day_map[row.created_at.date().isoformat()] += 1

    failures_by_day = [
        DailyFailureCount(day=day, count=count)
        for day, count in sorted(failures_by_day_map.items())
    ]

    return ExecutionMetricsResponse(
        window_days=window_days,
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        cancelled_runs=cancelled_runs,
        running_runs=running_runs,
        success_rate=success_rate,
        avg_duration_ms=avg_duration_ms,
        failures_by_day=failures_by_day,
    )


@router.get('/metrics', response_model=ExecutionMetricsResponse)
def get_execution_metrics(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> ExecutionMetricsResponse:
    window_start = datetime.now(UTC) - timedelta(days=days)
    rows = db.query(SubmissionRun).filter(SubmissionRun.created_at >= window_start).all()
    return _compute_execution_metrics(rows, window_days=days)


@router.get('/incidents', response_model=list[IncidentEventResponse])
def list_incidents(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: int | None = Query(default=None, ge=1),
    days: int | None = Query(default=None, ge=1, le=180),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[IncidentEventResponse]:
    query = db.query(AlertIncident)

    if cursor is not None:
        query = query.filter(AlertIncident.id < cursor)

    if days is not None:
        window_start = datetime.now(UTC) - timedelta(days=days)
        query = query.filter(AlertIncident.created_at >= window_start)

    if state:
        try:
            query = query.filter(AlertIncident.state == IncidentState(state))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='invalid incident state filter') from exc

    rows = query.order_by(AlertIncident.id.desc()).limit(limit).all()
    return [_incident_response(row) for row in rows]


@router.post('/incidents', response_model=IncidentEventResponse, status_code=201)
def create_incident(
    payload: IncidentEventCreateRequest,
    db: Session = Depends(get_db),
) -> IncidentEventResponse:
    row = AlertIncident(state=IncidentState(payload.state), message=payload.message)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _incident_response(row)


@router.get('/{run_id}', response_model=SubmissionRunDetailResponse)
def get_run(run_id: int, db: Session = Depends(get_db)) -> SubmissionRunDetailResponse:
    row = db.get(SubmissionRun, run_id)
    if not row:
        raise HTTPException(status_code=404, detail='run not found')

    return SubmissionRunDetailResponse(
        id=row.id,
        draft_id=row.draft_id,
        tinyfish_run_id=row.tinyfish_run_id,
        run_status=row.run_status.value,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
        streaming_url=row.streaming_url,
        error_message=row.error_message,
        created_at=row.created_at,
        result_json=row.result_json,
    )


@router.patch('/{run_id}/status', response_model=SubmissionRunStatusUpdateResponse)
def update_run_status(
    run_id: int,
    payload: SubmissionRunStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> SubmissionRunStatusUpdateResponse:
    row = db.get(SubmissionRun, run_id)
    if not row:
        raise HTTPException(status_code=404, detail='run not found')

    current = row.run_status
    target = RunStatus(payload.run_status)

    allowed_transitions: dict[RunStatus, set[RunStatus]] = {
        RunStatus.RUNNING: {RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.COMPLETED: {RunStatus.COMPLETED},
        RunStatus.FAILED: {RunStatus.FAILED, RunStatus.RUNNING},
        RunStatus.CANCELLED: {RunStatus.CANCELLED, RunStatus.RUNNING},
    }

    if target not in allowed_transitions[current]:
        raise HTTPException(
            status_code=409,
            detail=f'invalid transition from {current.value} to {target.value}',
        )

    _apply_status_timestamps(row, target)
    db.add(row)
    db.commit()
    db.refresh(row)

    return SubmissionRunStatusUpdateResponse(id=row.id, run_status=row.run_status.value)


@router.post('/run-sse')
async def run_sse(req: TinyFishRunRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    payload: dict[str, object] = {
        'url': req.url,
        'goal': req.goal,
        'browser_profile': req.browser_profile,
    }
    if req.proxy_config:
        payload['proxy_config'] = req.proxy_config

    run = SubmissionRun(draft_id=req.draft_id, run_status=RunStatus.RUNNING, started_at=datetime.now(UTC))
    db.add(run)
    db.commit()
    db.refresh(run)

    async def tracked_stream():
        async for line in stream_tinyfish_sse(payload):
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:].strip())
                    if event.get('type') == 'STARTED' and event.get('runId'):
                        run.tinyfish_run_id = event['runId']
                        db.add(run)
                        db.commit()
                    elif event.get('type') == 'STREAMING_URL' and event.get('streamingUrl'):
                        run.streaming_url = event['streamingUrl']
                        db.add(run)
                        db.commit()
                    elif event.get('type') == 'COMPLETE':
                        status = event.get('status')
                        target = RunStatus.COMPLETED if status == 'COMPLETED' else RunStatus.FAILED
                        _apply_status_timestamps(run, target)
                        run.result_json = event.get('resultJson')
                        if event.get('error'):
                            run.error_message = event['error'].get('message')
                        db.add(run)
                        db.commit()
                except Exception:
                    pass
            yield line

    return StreamingResponse(
        tracked_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Execution-Id': str(run.id),
        },
    )
