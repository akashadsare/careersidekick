from datetime import UTC, datetime

from app.db_models import AlertIncident, IncidentState
from app.routes.executions import create_incident, list_incidents
from app.models import IncidentEventCreateRequest


class FakeQuery:
    def __init__(self, rows: list[AlertIncident]):
        self._rows = rows
        self._limit: int | None = None

    def order_by(self, _clause):
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def all(self):
        sorted_rows = sorted(self._rows, key=lambda row: row.id, reverse=True)
        if self._limit is None:
            return sorted_rows
        return sorted_rows[: self._limit]


class FakeSession:
    def __init__(self, rows: list[AlertIncident] | None = None):
        self._rows = rows or []

    def query(self, _model):
        return FakeQuery(self._rows)

    def add(self, obj: AlertIncident):
        next_id = max([row.id for row in self._rows], default=0) + 1
        obj.id = next_id
        obj.created_at = datetime.now(UTC)
        self._rows.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


def _incident(incident_id: int, state: IncidentState, message: str) -> AlertIncident:
    return AlertIncident(
        id=incident_id,
        state=state,
        message=message,
        created_at=datetime(2026, 3, 16, 8, 0, tzinfo=UTC),
    )


def test_list_incidents_returns_most_recent_first() -> None:
    db = FakeSession(
        rows=[
            _incident(1, IncidentState.WARNING, 'drop detected'),
            _incident(2, IncidentState.CRITICAL, 'sustained degradation'),
            _incident(3, IncidentState.RECOVERED, 'recovered to normal'),
        ]
    )

    response = list_incidents(limit=2, db=db)

    assert len(response) == 2
    assert response[0].id == 3
    assert response[0].state == 'recovered'
    assert response[1].id == 2


def test_create_incident_persists_event() -> None:
    db = FakeSession(rows=[])

    response = create_incident(
        IncidentEventCreateRequest(state='muted', message='Critical alerts are muted.'),
        db,
    )

    assert response.id == 1
    assert response.state == 'muted'
    assert response.message == 'Critical alerts are muted.'
    assert response.created_at is not None
