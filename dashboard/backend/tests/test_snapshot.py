"""Background state collection: single-sampling of KPI history, refresh tiering,
degraded-mode publishing, and the version-based reader handoff."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from collectors.kpi_history import KpiHistory
from collectors.snapshot import StateSnapshotService, groups
from config import TOPOLOGIES


class _Counter:
    def __init__(self) -> None:
        self.calls = 0

    def bump(self) -> None:
        self.calls += 1


class _FakeDockerMonitor:
    def __init__(
        self,
        containers: list[dict[str, Any]],
        warnings: list[str] | None = None,
        names: set[str] | None = None,
        names_warning: str | None = None,
    ) -> None:
        self.containers = containers
        self.warnings = warnings or []
        self.names = {"oai-cu"} if names is None else names
        self.names_warning = names_warning
        self.collect_calls = _Counter()
        self.amf_calls = _Counter()

    def container_names(self):
        return (None if self.names_warning else set(self.names)), self.names_warning

    def collect(self, topology):
        self.collect_calls.bump()
        return list(self.containers), list(self.warnings)

    def amf_registration_events_seen(self):
        self.amf_calls.bump()
        return 3, None


class _FakeConfigParser:
    def __init__(self) -> None:
        self.calls = _Counter()

    def parse_f1(self):
        self.calls.bump()
        return {"cu": {}, "dus": []}, []


class _FakeResultsCollector:
    def __init__(self) -> None:
        self.calls = _Counter()

    def latest(self):
        self.calls.bump()
        return None, []


class _FakeHandoverEvents:
    def __init__(self) -> None:
        self.log_calls = _Counter()

    def collect_live_log_events(self, topology):
        self.log_calls.bump()
        return [], []

    def live_status(self, topology, containers, telnet, recent_events=None):
        return {"readiness": "degraded", "recent_events": recent_events or [], "warnings": []}


class _FakeOperatorOverview:
    def __init__(self) -> None:
        self.mobility_calls = _Counter()
        self.chart_calls = _Counter()

    def collect_live_mobility(self, topology, config):
        self.mobility_calls.bump()
        return None, []

    def collect_handover_chart(self, latest_run):
        self.chart_calls.bump()
        return None, []

    def build(self, **kwargs):
        return {"topology": kwargs["topology"].name}, []


class _FakeCampaigns:
    def __init__(self) -> None:
        self.calls = _Counter()

    def websocket_summary(self):
        self.calls.bump()
        return {"campaigns": []}


class _FakeLiveLatency:
    def __init__(self) -> None:
        self.calls = _Counter()

    async def sample(self, containers=None, topology=None):
        self.calls.bump()
        return None

    def state(self):
        return {"samples": [], "warnings": [], "probing": True, "skip_reason": None}


class _FakeActionManager:
    def actions_summary(self):
        return {"enabled": False, "running_job": None, "recent_jobs": []}


async def _telnet_state():
    return {"cu": {"reachable": False, "last_checked": "2026-08-10T00:00:00Z", "attached_ues": []}}


def _service(tmp_path: Path, **overrides: Any) -> StateSnapshotService:
    defaults = dict(
        repo_root=tmp_path,
        topology_provider=lambda: TOPOLOGIES["f1"],
        docker_monitor=_FakeDockerMonitor([{"name": "oai-cu", "role": "cu", "status": "running", "indicator": "green", "required": True}]),
        config_parser=_FakeConfigParser(),
        results_collector=_FakeResultsCollector(),
        handover_events=_FakeHandoverEvents(),
        operator_overview=_FakeOperatorOverview(),
        campaigns=_FakeCampaigns(),
        kpi_history=KpiHistory(),
        live_latency_monitor=_FakeLiveLatency(),
        action_manager=_FakeActionManager(),
        telnet_state=_telnet_state,
        fast_interval_seconds=0.01,
        medium_interval_seconds=1000.0,
        slow_interval_seconds=1000.0,
    )
    defaults.update(overrides)
    return StateSnapshotService(**defaults)


def test_one_kpi_sample_per_refresh_regardless_of_readers(tmp_path):
    """The regression this collector exists to fix: sampling used to happen inside the
    per-reader rebuild, so history density scaled with the number of open browser tabs."""

    async def scenario():
        service = _service(tmp_path)
        for _ in range(3):
            await service.refresh()
        # Many readers, no extra samples.
        for _ in range(10):
            service.current()
        return service.kpi_history.samples()

    samples = asyncio.run(scenario())
    assert len(samples) == 3


def test_slow_and_medium_sources_are_cached_between_fast_cycles(tmp_path):
    async def scenario():
        service = _service(tmp_path)
        for _ in range(5):
            await service.refresh()
        return service

    service = asyncio.run(scenario())
    # Fast tier runs every cycle.
    assert service.docker_monitor.collect_calls.calls == 5
    assert service.live_latency_monitor.calls.calls == 5
    # Medium and slow tiers collected once, then served from cache.
    assert service.handover_events.log_calls.calls == 1
    assert service.docker_monitor.amf_calls.calls == 1
    assert service.operator_overview.mobility_calls.calls == 1
    assert service.config_parser.calls.calls == 1
    assert service.results_collector.calls.calls == 1
    assert service.operator_overview.chart_calls.calls == 1
    assert service.campaigns.calls.calls == 1


def test_new_run_directory_invalidates_the_slow_tier(tmp_path):
    """A finished experiment should appear without waiting out the slow interval."""
    runs_dir = tmp_path / "results" / "runs"
    runs_dir.mkdir(parents=True)

    async def scenario():
        service = _service(tmp_path)
        await service.refresh()
        before = service.results_collector.calls.calls
        (runs_dir / "20260810_000000_f1_handover_smoke").mkdir()
        await service.refresh()
        return before, service.results_collector.calls.calls

    before, after = asyncio.run(scenario())
    assert before == 1
    assert after == 2


def test_topology_switch_is_detected_and_drops_cached_tier_data(tmp_path):
    """After a teardown/deploy the dashboard must follow the new stack, and must not
    attribute the previous topology's cached config or log events to it."""
    monitor = _FakeDockerMonitor(
        [{"name": "oai-cu", "role": "cu", "status": "running", "indicator": "green", "required": True}],
        names={"oai-cu"},
    )

    async def scenario():
        service = _service(tmp_path, docker_monitor=monitor)
        first = await service.refresh()
        monitor.names = {"oai-gnb0", "oai-gnb1"}
        second = await service.refresh()
        return first, second, service

    first, second, service = asyncio.run(scenario())
    assert first["topology"] == "f1"
    assert second["topology"] == "n2-monolithic"
    assert second["topology_detection"]["detected"] == "n2-monolithic"
    # Slow and medium tiers re-collected for the new topology instead of serving F1 data.
    assert service.results_collector.calls.calls == 2
    assert service.handover_events.log_calls.calls == 2
    # Config parsing is F1-only, so N2 gets the honest placeholder rather than F1's
    # cell configuration carried over from the previous topology.
    assert second["config"]["topology"] == "n2-monolithic"
    assert service.config_parser.calls.calls == 1


def test_idle_host_reports_idle_not_degraded(tmp_path):
    """Nothing deployed is a normal state. The required containers are legitimately
    absent, so reporting "degraded" made a clean machine look broken."""
    monitor = _FakeDockerMonitor(
        [{"name": "oai-cu", "role": "cu", "status": "missing", "indicator": "red", "required": True, "exists": False}],
        names=set(),
    )

    async def scenario():
        service = _service(tmp_path, docker_monitor=monitor)
        return await service.refresh()

    state = asyncio.run(scenario())
    assert state["status"] == "idle"
    assert state["warnings"] == []
    assert state["topology_detection"]["detected"] is None
    assert "No testbed containers are running" in state["topology_detection"]["note"]


def test_running_ran_reports_ok(tmp_path):
    monitor = _FakeDockerMonitor(
        [{"name": "oai-cu", "role": "cu", "status": "running", "indicator": "green", "required": True, "exists": True}],
        names={"oai-cu"},
    )

    async def scenario():
        service = _service(tmp_path, docker_monitor=monitor)
        return await service.refresh()

    assert asyncio.run(scenario())["status"] == "ok"


def test_deployed_but_broken_still_reports_degraded(tmp_path):
    """A half-up stack must not be softened into "idle" by the new branch."""
    monitor = _FakeDockerMonitor(
        [
            {"name": "oai-cu", "role": "cu", "status": "running", "indicator": "green", "required": True, "exists": True},
            {"name": "oai-du0", "role": "du", "status": "exited", "indicator": "red", "required": True, "exists": True},
        ],
        names={"oai-cu"},
    )

    async def scenario():
        service = _service(tmp_path, docker_monitor=monitor)
        return await service.refresh()

    assert asyncio.run(scenario())["status"] == "degraded"


def test_publishes_degraded_snapshot_when_docker_is_unavailable(tmp_path):
    """The dashboard must still serve state with the testbed and Docker down."""
    monitor = _FakeDockerMonitor(
        [{"name": "oai-cu", "role": "cu", "status": "docker_unavailable", "indicator": "red", "required": True}],
        warnings=["Docker API unavailable: boom"],
        names_warning="Docker API unavailable for topology detection: boom",
    )

    async def scenario():
        service = _service(tmp_path, docker_monitor=monitor)
        return await service.refresh()

    state = asyncio.run(scenario())
    assert state["status"] == "degraded"
    assert any("Docker API unavailable" in warning for warning in state["warnings"])
    assert state["topology"] == "f1"


def test_wait_for_next_returns_current_snapshot_without_waiting(tmp_path):
    """A newly connected reader gets the current state immediately, not after a cycle."""

    async def scenario():
        service = _service(tmp_path)
        await service.refresh()
        return await asyncio.wait_for(service.wait_for_next(-1), timeout=1.0)

    version, state = asyncio.run(scenario())
    assert version == 1
    assert state["topology"] == "f1"


def test_collector_failure_is_surfaced_not_swallowed(tmp_path):
    async def scenario():
        service = _service(tmp_path)
        await service.refresh()
        await service._publish_collector_failure(RuntimeError("cycle exploded"))
        return service.current()

    state = asyncio.run(scenario())
    assert state["status"] == "degraded"
    assert any("cycle exploded" in warning for warning in state["warnings"])


def test_starting_snapshot_is_served_before_first_collection(tmp_path):
    service = _service(tmp_path)
    state = service.current()
    assert state["topology"] == "f1"
    assert state["containers"] == []
    assert any("has not completed" in warning for warning in state["warnings"])


def test_groups_partitions_core_and_roles():
    containers = [
        {"name": "oai-amf", "role": "core", "status": "running", "indicator": "green"},
        {"name": "oai-cu", "role": "cu", "status": "running", "indicator": "orange"},
    ]
    result = groups(containers)
    assert result["cn5g"]["containers"] == ["oai-amf"]
    assert result["cn5g"]["running"] == 1
    assert sorted(result["roles"]) == ["core", "cu"]
