import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.routes import agent as agent_mod
from app.db.models.agent_run import AgentRun
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _run(status="running", progress=10, phase="seo_analysis") -> AgentRun:
    run = AgentRun(
        store_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        run_type="seo_analysis",
        status=status,
        progress_pct=progress,
        current_phase=phase,
        credits_reserved=2,
        credits_used=0,
    )
    run.id = uuid.uuid4()
    run.created_at = datetime.now(timezone.utc)
    return run


def _events(stream) -> list[dict]:
    return [json.loads(chunk.removeprefix("data: ")) for chunk in stream]


def _wire_stream_db(monkeypatch, run_provider):
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.side_effect = run_provider

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(agent_mod, "get_db_session", fake_session)


def test_agent_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/agent/runs/{run_id}" in paths
    assert "/v1/agent/runs/{run_id}/stream" in paths


def test_get_run_returns_status(monkeypatch):
    run = _run(status="completed", progress=100, phase=None)
    user = MagicMock(id=run.user_id)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = run
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    resp = TestClient(app).get(f"/v1/agent/runs/{run.id}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert data["progress_pct"] == 100
    assert data["credits_reserved"] == 2


def test_get_run_404_when_not_owned():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=uuid.uuid4())
    app.dependency_overrides[get_db] = lambda: db

    resp = TestClient(app).get(f"/v1/agent/runs/{uuid.uuid4()}")

    assert resp.status_code == 404


def test_stream_401_with_invalid_token(monkeypatch):
    monkeypatch.setattr(agent_mod, "decode_token", lambda token: None)
    app.dependency_overrides[get_db] = lambda: MagicMock()

    resp = TestClient(app).get(
        f"/v1/agent/runs/{uuid.uuid4()}/stream", params={"token": "bad"}
    )

    assert resp.status_code == 401


def test_stream_emits_connected_then_completed(monkeypatch):
    run = _run(status="completed", progress=100, phase=None)
    run.result_summary = {"overall_score": 70, "priority": "high"}
    _wire_stream_db(monkeypatch, lambda: run)

    events = _events(agent_mod.run_event_stream(str(run.id), poll_interval=0))

    assert [e["type"] for e in events] == ["connected", "completed"]
    assert events[1]["result"] == {"overall_score": 70, "priority": "high"}
    assert events[1]["progress"] == 100


def test_stream_emits_progress_changes_until_failure(monkeypatch):
    run = _run(status="running", progress=10)
    states = iter(
        [
            ("running", 10, "seo_analysis"),
            ("running", 10, "seo_analysis"),  # unchanged -> no event
            ("running", 60, "seo_analysis"),
            ("failed", 60, None),
        ]
    )

    def provider():
        try:
            run.status, run.progress_pct, run.current_phase = next(states)
        except StopIteration:
            pass
        run.error_message = "AI refused" if run.status == "failed" else None
        return run

    _wire_stream_db(monkeypatch, provider)

    events = _events(agent_mod.run_event_stream(str(run.id), poll_interval=0))

    types = [e["type"] for e in events]
    assert types == ["connected", "progress", "progress", "failed"]
    assert events[1]["progress"] == 10
    assert events[2]["progress"] == 60
    assert events[3]["error"] == "AI refused"


def test_stream_fails_when_run_missing(monkeypatch):
    _wire_stream_db(monkeypatch, lambda: None)

    events = _events(agent_mod.run_event_stream(str(uuid.uuid4()), poll_interval=0))

    assert [e["type"] for e in events] == ["connected", "failed"]


def test_stream_times_out(monkeypatch):
    run = _run(status="running", progress=10)
    _wire_stream_db(monkeypatch, lambda: run)

    events = _events(
        agent_mod.run_event_stream(str(run.id), poll_interval=0, max_seconds=0.01)
    )

    assert events[-1]["type"] == "timeout"
