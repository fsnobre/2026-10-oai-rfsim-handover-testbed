"""HTTP-level route tests: snapshot-backed endpoints, the optional bearer-token
dependency, and the ActionError -> HTTPException mapping.

These deliberately do not run the application lifespan, so the background collector
never starts and the tests stay hermetic — no Docker daemon, no testbed. Endpoints
therefore serve the pre-collection snapshot, which is itself a shape worth asserting:
the dashboard is expected to answer before (and without) a working testbed.
"""

from __future__ import annotations

import main
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_topology_serves_snapshot_shape(client):
    body = client.get("/api/topology").json()
    for key in ("timestamp", "topology", "status", "containers", "groups", "warnings", "freshness"):
        assert key in body, f"missing key: {key}"


def test_overview_and_handover_read_the_same_snapshot(client):
    assert "overview" in client.get("/api/overview").json()
    assert "handover" in client.get("/api/handover").json()


def test_missing_run_returns_null_not_error(client):
    body = client.get("/api/runs/definitely-not-a-run").json()
    assert body["run"] is None
    assert body["warnings"]


def test_capabilities_open_when_auth_disabled(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    response = client.get("/api/actions/capabilities")
    assert response.status_code == 200
    assert response.json()["actions_enabled"] is False


def test_action_endpoints_require_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "s3cret")

    assert client.get("/api/actions/capabilities").status_code == 401
    assert client.get("/api/actions/capabilities", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/actions/capabilities", headers={"Authorization": "s3cret"}).status_code == 401

    ok = client.get("/api/actions/capabilities", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_read_endpoints_are_unauthenticated_by_design(client, monkeypatch):
    """Only /api/actions/* and /ws are guarded; read endpoints stay open. Asserted so
    that widening auth coverage later is a deliberate, visible change."""
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "s3cret")
    assert client.get("/api/topology").status_code == 200
    assert client.get("/api/runs").status_code == 200


def test_confirm_is_required(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    response = client.post("/api/actions/trigger-handover", json={})
    assert response.status_code == 400
    assert "confirm" in response.json()["detail"]


def test_actions_disabled_returns_403(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    response = client.post("/api/actions/trigger-handover", json={"confirm": True})
    assert response.status_code == 403
    assert "DASHBOARD_ENABLE_ACTIONS" in response.json()["detail"]


def test_unknown_topology_is_rejected(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    monkeypatch.setattr(main.action_manager, "actions_enabled", True)
    response = client.post("/api/actions/smoke-test", json={"confirm": True, "topology": "rm -rf"})
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_repeated_smoke_count_must_be_an_integer(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    monkeypatch.setattr(main.action_manager, "actions_enabled", True)
    response = client.post(
        "/api/actions/repeated-smoke-test", json={"confirm": True, "topology": "f1", "count": "many"}
    )
    assert response.status_code == 400
    assert "integer" in response.json()["detail"]


def test_unknown_job_returns_404(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    assert client.get("/api/actions/jobs/nope").status_code == 404


def test_websocket_sends_a_snapshot(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "")
    with client.websocket_connect("/ws") as socket:
        state = socket.receive_json()
    assert state["topology"]
    assert "containers" in state


def test_websocket_rejects_a_bad_token(client, monkeypatch):
    monkeypatch.setattr(main, "DASHBOARD_API_TOKEN", "s3cret")
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=wrong") as socket:
            socket.receive_json()
