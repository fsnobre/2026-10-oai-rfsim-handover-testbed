"""Repository-root host visibility: the guard that stops compose-spawning actions from
resolving bind mounts against a path that only exists inside the backend container."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from actions import COMPOSE_SPAWNING_KINDS, ActionError, ActionManager
from host_mounts import host_repo_root_status

# The exact layout of dashboard/docker-compose.dashboard.yml: repo bind-mounted at /repo.
CONTAINER_ALIAS_MOUNTS = [
    {"Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock"},
    {"Source": "/home/user/oai-rfsim-handover-testbed", "Destination": "/repo"},
    {"Source": "/home/user/oai-rfsim-handover-testbed/results", "Destination": "/repo/results"},
]

# The layout of the host-actions override: identical source and destination.
HOST_PATH_MOUNTS = [
    {"Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock"},
    {"Source": "/home/user/oai-rfsim-handover-testbed", "Destination": "/home/user/oai-rfsim-handover-testbed"},
]


def test_container_alias_is_detected_as_not_host_visible():
    status = host_repo_root_status("/repo", mounts=CONTAINER_ALIAS_MOUNTS, in_container=True)
    assert status["host_visible"] is False
    assert status["verified"] is True
    assert status["host_path"] == "/home/user/oai-rfsim-handover-testbed"
    assert "host-actions.example.yml" in status["detail"]


def test_host_actions_override_is_host_visible():
    status = host_repo_root_status(
        "/home/user/oai-rfsim-handover-testbed", mounts=HOST_PATH_MOUNTS, in_container=True
    )
    assert status["host_visible"] is True
    assert status["verified"] is True
    assert status["detail"] is None


def test_running_outside_a_container_needs_no_translation():
    status = host_repo_root_status("/home/user/repo", in_container=False)
    assert status["host_visible"] is True
    assert status["verified"] is True


def test_unknown_mounts_do_not_block():
    """Blocking requires positive evidence; an uninspectable setup keeps working."""
    for mounts in (None, []):
        status = host_repo_root_status("/repo", mounts=mounts, in_container=True)
        assert status["host_visible"] is True
        assert status["verified"] is False


def test_nested_repo_root_translates_through_the_parent_mount():
    status = host_repo_root_status(
        "/repo/nested", mounts=[{"Source": "/srv/checkout", "Destination": "/repo"}], in_container=True
    )
    assert status["host_visible"] is False
    assert status["host_path"] == "/srv/checkout/nested"


def _manager(status: dict) -> ActionManager:
    manager = ActionManager(
        Path("/repo"),
        actions_enabled=True,
        trigger_timeout_seconds=10,
        measure_interruption_timeout_seconds=10,
        smoke_timeout_seconds=10,
        repeated_smoke_timeout_seconds=10,
    )
    manager._repo_root_status = status
    return manager


BROKEN = {
    "host_visible": False,
    "verified": True,
    "repo_root": "/repo",
    "host_path": "/home/user/repo",
    "detail": "use the host-actions override",
}


@pytest.mark.parametrize(
    "call",
    [
        lambda m: m.start_deploy_topology(confirm=True, topology="f1"),
        lambda m: m.start_teardown_topology(confirm=True, topology="f1"),
        lambda m: m.start_smoke_test(confirm=True, topology="f1"),
        lambda m: m.start_repeated_smoke_test(confirm=True, topology="f1", count=2),
    ],
)
def test_compose_spawning_actions_are_refused(call):
    manager = _manager(BROKEN)
    with pytest.raises(ActionError) as excinfo:
        asyncio.run(call(manager))
    assert excinfo.value.status_code == 409
    assert "host-actions" in excinfo.value.message
    # Refused before starting anything.
    assert manager.jobs() == []


def test_telnet_only_actions_are_unaffected():
    """trigger_handover and measure_interruption do not spawn compose, so the mount
    layout is irrelevant to them."""
    assert "trigger_handover" not in COMPOSE_SPAWNING_KINDS
    assert "measure_interruption" not in COMPOSE_SPAWNING_KINDS


def test_capabilities_reports_the_problem_and_disables_compose_actions():
    capabilities = _manager(BROKEN).capabilities()
    assert capabilities["actions_enabled"] is True
    assert capabilities["environment"]["repo_root_host_visible"] is False
    assert capabilities["runtime_checks"]["repo_root_host_visible"] is False

    by_kind = {item["kind"]: item for item in capabilities["available_actions"]}
    for kind in COMPOSE_SPAWNING_KINDS:
        assert by_kind[kind]["enabled"] is False, kind
        assert "not visible to the host" in by_kind[kind]["reason"], kind
    # Telnet-only actions stay available.
    assert by_kind["trigger_handover"]["enabled"] is True


def test_capabilities_are_normal_when_the_repo_root_is_host_visible():
    healthy = {
        "host_visible": True,
        "verified": True,
        "repo_root": "/repo",
        "host_path": "/repo",
        "detail": None,
    }
    capabilities = _manager(healthy).capabilities()
    by_kind = {item["kind"]: item for item in capabilities["available_actions"]}
    for kind in COMPOSE_SPAWNING_KINDS:
        assert by_kind[kind]["enabled"] is True, kind
    assert capabilities["runtime_checks"]["repo_root_host_visible"] is True
