"""Background state collection.

Every dashboard reader — the WebSocket and the state-backed REST endpoints — used to
rebuild the whole state inline, which meant the cost scaled with the number of readers
and the blocking Docker SDK calls ran on the event loop. This module collects once, in
a single background task, and publishes an immutable snapshot that readers just read.

Two properties matter beyond raw efficiency:

* **Blocking work stays off the event loop.** The ``docker`` SDK and every artifact read
  are synchronous, so they are dispatched through ``asyncio.to_thread``.
* **KPI history is sampled by the collector, not by readers.** Sampling used to happen
  inside the per-reader rebuild, so the series density depended on how many browser tabs
  were open. Exactly one sample is now recorded per fast-tier cycle.

Sources are grouped into refresh tiers by how fast they actually change; the assembled
snapshot shape is identical to what the previous inline builder produced.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Awaitable, Callable

from config import TOPOLOGY_PIN, topology_by_name
from state_models import live_kpis_from_sources, source_freshness, utc_now

from collectors.kpi_history import sample_from_state
from collectors.topology_detector import resolve_topology

# Bound on how long startup waits for the first collection before serving the
# placeholder snapshot instead. Keeps a hung Docker daemon from blocking startup.
FIRST_REFRESH_TIMEOUT_SECONDS = 15.0

CN_CONTAINER_NAMES = frozenset(
    {"mysql", "oai-nrf", "oai-udr", "oai-udm", "oai-ausf", "oai-amf", "oai-smf", "oai-upf"}
)


def groups(containers: list[dict[str, Any]]) -> dict[str, Any]:
    cn = [item for item in containers if item["name"] in CN_CONTAINER_NAMES]
    by_role: dict[str, list[dict[str, Any]]] = {}
    for item in containers:
        by_role.setdefault(item["role"], []).append(item)
    return {
        "cn5g": {
            "containers": [item["name"] for item in cn],
            "running": sum(1 for item in cn if item.get("status") == "running"),
            "total": len(cn),
            "indicator": "green" if cn and all(item.get("indicator") in {"green", "orange"} for item in cn) else "red",
        },
        "roles": by_role,
    }


class _Tier:
    """A cached group of sources refreshed on its own interval."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self._refreshed_at: float | None = None

    def is_stale(self, now: float) -> bool:
        return self._refreshed_at is None or (now - self._refreshed_at) >= self.interval_seconds

    def mark(self, now: float) -> None:
        self._refreshed_at = now

    def invalidate(self) -> None:
        self._refreshed_at = None


class StateSnapshotService:
    """Owns the background collection loop and the published snapshot."""

    def __init__(
        self,
        *,
        repo_root: Path,
        topology_provider: Callable[[], Any],
        docker_monitor: Any,
        config_parser: Any,
        results_collector: Any,
        handover_events: Any,
        operator_overview: Any,
        campaigns: Any,
        kpi_history: Any,
        live_latency_monitor: Any,
        action_manager: Any,
        telnet_state: Callable[[], Awaitable[dict[str, Any]]],
        fast_interval_seconds: float,
        medium_interval_seconds: float,
        slow_interval_seconds: float,
    ) -> None:
        self.repo_root = repo_root
        self.topology_provider = topology_provider
        self.docker_monitor = docker_monitor
        self.config_parser = config_parser
        self.results_collector = results_collector
        self.handover_events = handover_events
        self.operator_overview = operator_overview
        self.campaigns = campaigns
        self.kpi_history = kpi_history
        self.live_latency_monitor = live_latency_monitor
        self.action_manager = action_manager
        self.telnet_state = telnet_state
        self.fast_interval_seconds = fast_interval_seconds

        self._medium = _Tier(medium_interval_seconds)
        self._slow = _Tier(slow_interval_seconds)
        self._medium_data: dict[str, Any] = {}
        self._slow_data: dict[str, Any] = {}
        self._runs_dir = repo_root / "results" / "runs"
        self._runs_mtime: float | None = None
        self._last_topology_name: str | None = None

        self._snapshot: dict[str, Any] = self._starting_snapshot()
        self._version = 0
        self._condition = asyncio.Condition()
        self._task: asyncio.Task[None] | None = None

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Collect once (best effort, time-bounded) and then run the loop."""
        with contextlib.suppress(asyncio.TimeoutError, Exception):
            await asyncio.wait_for(self.refresh(), timeout=FIRST_REFRESH_TIMEOUT_SECONDS)
        self._task = asyncio.create_task(self._run(), name="dashboard-state-collector")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.refresh()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # never let one bad cycle kill collection
                await self._publish_collector_failure(exc)
            await asyncio.sleep(self.fast_interval_seconds)

    # -- readers -----------------------------------------------------------

    def current(self) -> dict[str, Any]:
        return self._snapshot

    async def wait_for_next(self, last_version: int) -> tuple[int, dict[str, Any]]:
        """Block until a snapshot newer than ``last_version`` is published.

        Returns immediately when one already exists, so a fresh reader gets the current
        state without waiting a full cycle.
        """
        async with self._condition:
            await self._condition.wait_for(lambda: self._version > last_version)
            return self._version, self._snapshot

    # -- collection --------------------------------------------------------

    async def refresh(self) -> dict[str, Any]:
        now = asyncio.get_running_loop().time()
        warnings: list[str] = []

        # Resolve the topology before inspecting containers, so a deploy or teardown is
        # picked up without a backend restart.
        names, name_warning = await asyncio.to_thread(self.docker_monitor.container_names)
        detection = resolve_topology(names, pinned=TOPOLOGY_PIN, warning=name_warning)
        topology = topology_by_name(detection["topology"])
        if detection.get("warning"):
            warnings.append(detection["warning"])
        if detection["topology"] != self._last_topology_name:
            # Cached tier data describes the previous topology; drop it so nothing stale
            # is attributed to the new one.
            self._invalidate_tiers()
            self._last_topology_name = detection["topology"]

        containers, docker_warnings = await asyncio.to_thread(self.docker_monitor.collect, topology)
        warnings.extend(docker_warnings)
        docker_checked_at = utc_now()

        telnet = await self.telnet_state()
        cu_warning = telnet.get("cu", {}).get("warning")
        if cu_warning:
            warnings.append(cu_warning)
        telnet_checked_at = telnet.get("cu", {}).get("last_checked")

        if self._slow.is_stale(now) or self._runs_changed():
            await self._refresh_slow(topology)
            self._slow.mark(now)
        if self._medium.is_stale(now):
            await self._refresh_medium(topology)
            self._medium.mark(now)

        warnings.extend(self._slow_data.get("warnings", []))
        warnings.extend(self._medium_data.get("warnings", []))

        parsed_config = self._slow_data.get("config", {})
        latest_run = self._slow_data.get("latest_run")

        live_kpis = live_kpis_from_sources(
            telnet.get("cu", {}),
            self._medium_data.get("amf_registration_events_seen"),
        )
        handover = self.handover_events.live_status(
            topology,
            containers,
            telnet,
            recent_events=self._medium_data.get("live_log_events", []),
        )
        warnings.extend(handover.get("warnings", []))

        actions = self.action_manager.actions_summary()

        await self.live_latency_monitor.sample(containers=containers, topology=topology)
        live_latency = self.live_latency_monitor.state()

        overview, overview_warnings = self.operator_overview.build(
            topology=topology,
            containers=containers,
            config=parsed_config,
            live_kpis=live_kpis,
            latest_run=latest_run,
            handover=handover,
            actions=actions,
            live_latency=live_latency,
            live_mobility=self._medium_data.get("live_mobility"),
            handover_chart=self._slow_data.get("handover_chart"),
        )
        warnings.extend(overview_warnings)

        telnet_for_history = {
            **telnet,
            "cu": {
                **telnet.get("cu", {}),
                "ue_count": live_kpis["ue_count"],
                "ue_count_source": live_kpis["ue_count_source"],
            },
        }
        sample = self.kpi_history.add(
            sample_from_state(containers, telnet_for_history, latest_run, live_kpis)
        )
        history = self.kpi_history.samples()

        # An idle host reports "idle", not "degraded": with nothing deployed the required
        # containers are legitimately absent, and calling that degraded makes a clean
        # machine look broken. Real problems still surface as warnings, which dominate.
        ran_deployed = any(
            item.get("exists") and item.get("role") in {"cu", "du", "gnb", "ue"} for item in containers
        )
        red_required = any(item.get("required") and item.get("indicator") == "red" for item in containers)
        if warnings:
            status = "degraded"
        elif not ran_deployed:
            status = "idle"
        elif red_required:
            status = "degraded"
        else:
            status = "ok"

        state = {
            "timestamp": utc_now(),
            "topology": topology.name,
            "topology_detection": detection,
            "radio_mode": topology.radio_mode,
            "handover_type": topology.handover_type,
            "status": status,
            "containers": containers,
            "groups": groups(containers),
            "config": parsed_config,
            "telnet": telnet,
            "live_kpis": live_kpis,
            "latest_run": latest_run,
            "handover": handover,
            "overview": overview,
            "live_latency": live_latency,
            "campaigns": self._slow_data.get("campaigns"),
            "actions": actions,
            "kpi_history": history[-120:],
            "latest_sample": sample,
            "freshness": source_freshness(
                docker=docker_checked_at,
                config=self._slow_data.get("checked_at"),
                telnet=telnet_checked_at,
                results=self._slow_data.get("checked_at"),
            ),
            "warnings": warnings,
        }
        await self._publish(state)
        return state

    async def _refresh_medium(self, topology: Any) -> None:
        """Bounded Docker log reads: recent handover events, AMF registrations, CU mobility."""
        warnings: list[str] = []

        events, event_warnings = await asyncio.to_thread(
            self.handover_events.collect_live_log_events, topology
        )
        warnings.extend(event_warnings)

        amf_seen, amf_warning = await asyncio.to_thread(self.docker_monitor.amf_registration_events_seen)
        if amf_warning:
            warnings.append(amf_warning)

        mobility, mobility_warnings = await asyncio.to_thread(
            self.operator_overview.collect_live_mobility, topology, self._slow_data.get("config", {})
        )
        warnings.extend(mobility_warnings)

        self._medium_data = {
            "live_log_events": events,
            "amf_registration_events_seen": amf_seen,
            "live_mobility": mobility,
            "warnings": warnings,
        }

    async def _refresh_slow(self, topology: Any) -> None:
        """Config and artifact scans: parsed config, run list, latest run, campaigns."""
        warnings: list[str] = []

        if topology.name == "f1":
            parsed_config, config_warnings = await asyncio.to_thread(self.config_parser.parse_f1)
        else:
            # A known scope limit, not an anomaly: carried as a note on the config the UI
            # already renders, rather than a warning that would mark a healthy stack
            # degraded for as long as a non-F1 topology is running.
            parsed_config = {
                "topology": topology.name,
                "status": "not_parsed",
                "note": f"Cell configuration parsing is implemented for F1 only; {topology.name} is not parsed.",
            }
            config_warnings = []
        warnings.extend(config_warnings)

        latest_run, result_warnings = await asyncio.to_thread(self.results_collector.latest)
        warnings.extend(result_warnings)

        chart, chart_warnings = await asyncio.to_thread(
            self.operator_overview.collect_handover_chart, latest_run
        )
        warnings.extend(chart_warnings)

        campaigns = await asyncio.to_thread(self.campaigns.websocket_summary)

        self._slow_data = {
            "config": parsed_config,
            "latest_run": latest_run,
            "handover_chart": chart,
            "campaigns": campaigns,
            "checked_at": utc_now(),
            "warnings": warnings,
        }

    def _invalidate_tiers(self) -> None:
        self._medium.invalidate()
        self._slow.invalidate()
        self._medium_data = {}
        self._slow_data = {}

    def _runs_changed(self) -> bool:
        """Detect a new run directory so a finished experiment shows up promptly
        instead of waiting out the slow tier."""
        try:
            mtime = self._runs_dir.stat().st_mtime
        except OSError:
            return False
        if mtime != self._runs_mtime:
            self._runs_mtime = mtime
            return True
        return False

    # -- publishing --------------------------------------------------------

    async def _publish(self, state: dict[str, Any]) -> None:
        async with self._condition:
            self._snapshot = state
            self._version += 1
            self._condition.notify_all()

    async def _publish_collector_failure(self, exc: Exception) -> None:
        """Surface a collector-level failure rather than silently serving stale state."""
        state = dict(self._snapshot)
        state["status"] = "degraded"
        state["timestamp"] = utc_now()
        state["warnings"] = [
            *state.get("warnings", []),
            f"State collector cycle failed: {exc}",
        ]
        await self._publish(state)

    def _starting_snapshot(self) -> dict[str, Any]:
        topology = self.topology_provider()
        return {
            "timestamp": utc_now(),
            "topology": topology.name,
            "topology_detection": {
                "topology": topology.name,
                "mode": "pinned" if TOPOLOGY_PIN else "auto",
                "detected": None,
                "source": "startup",
                "warning": None,
            },
            "radio_mode": topology.radio_mode,
            "handover_type": topology.handover_type,
            "status": "degraded",
            "containers": [],
            "groups": groups([]),
            "config": {},
            "telnet": {"cu": {}},
            "live_kpis": live_kpis_from_sources({}, None),
            "latest_run": None,
            "handover": {},
            "overview": {},
            "live_latency": None,
            "campaigns": None,
            "actions": self.action_manager.actions_summary(),
            "kpi_history": [],
            "latest_sample": None,
            "freshness": source_freshness(docker=None, config=None, telnet=None, results=None),
            "warnings": ["Initial state collection has not completed yet."],
        }
