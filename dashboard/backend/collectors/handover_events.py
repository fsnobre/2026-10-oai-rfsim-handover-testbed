from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import docker
    from docker.errors import DockerException, NotFound
except ModuleNotFoundError:  # pragma: no cover - exercised by lightweight validation environments
    docker = None

    class DockerException(Exception):
        pass

    class NotFound(DockerException):
        pass

from config import TopologyConfig

# Distinguishes "caller supplied nothing" from "caller supplied an empty list".
_UNSET = object()


def telnet_observation(cu: dict[str, Any]) -> str:
    """Classify what is actually known about the telnet control node.

    "Not reachable" and "never probed" are different claims. Passive polling is disabled
    by default (repeated telnet probes have destabilised some OAI CU builds) and some
    topologies have no telnet node at all; reporting either as unreachable asserts a
    failure that was never observed.

    Returns one of ``reachable``, ``unreachable``, ``polling_disabled``, ``no_endpoint``.
    """
    if cu.get("reachable"):
        return "reachable"
    if cu.get("polling_enabled") is False:
        return "no_endpoint" if cu.get("host") is None else "polling_disabled"
    return "unreachable"

SUMMARY_METRICS = [
    "estimated_interruption_ms",
    "first_ping_after_handover_ms",
    "packet_loss_percent",
    "rtt_min_ms",
    "rtt_avg_ms",
    "rtt_max_ms",
    "iperf_mbps",
    "iperf_jitter_ms",
    "iperf_lost_percent",
]

EVENT_CATEGORY = {
    "smoke_start": "trigger",
    "ue_data_ready_start": "data_plane",
    "ue_data_ready_passed": "data_plane",
    "ping_precheck_start": "data_plane",
    "ping_precheck_passed": "data_plane",
    "ping_capture_start": "data_plane",
    "ping_capture_stop": "data_plane",
    "before_handover": "trigger",
    "handover_trigger_start": "trigger",
    "handover_trigger_end": "trigger",
    "handover_trigger_failed": "trigger",
    "after_handover": "trigger",
    "iperf_server_start": "data_plane",
    "iperf_client_start": "data_plane",
    "iperf_client_end": "data_plane",
    "ping_metrics_invalid": "metric",
    "smoke_end": "trigger",
}

MESSAGE_FLOW_MAP = {
    "ping_capture_start": ("UE", "EXT-DN"),
    "ping_capture_stop": ("UE", "EXT-DN"),
    "iperf_client_start": ("UE", "EXT-DN"),
    "iperf_client_end": ("UE", "EXT-DN"),
    "first_ping_after_handover": ("EXT-DN", "UE"),
}


def _short(value: str | None, limit: int = 240) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _duration_seconds(start: str | None, end: str | None) -> float | None:
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    if not start_dt or not end_dt:
        return None
    return max(0.0, (end_dt - start_dt).total_seconds())


def _numeric(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"Missing optional artifact: {path.name}"
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:
        return None, f"Could not parse {path.name}: {exc}"


def _read_events(path: Path) -> tuple[list[dict[str, str]], str | None]:
    if not path.exists():
        return [], "Missing optional artifact: events.csv"
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"timestamp", "event", "details"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                return [], f"Could not parse events.csv: missing columns {', '.join(sorted(required))}"
            return list(reader), None
    except Exception as exc:
        return [], f"Could not parse events.csv: {exc}"


def _read_ping_samples(path: Path, limit: int = 600) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], "Missing optional artifact: ping.csv"
    try:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception as exc:
        return [], f"Could not parse ping.csv: {exc}"

    if len(rows) > limit:
        step = max(1, len(rows) // limit)
        rows = rows[::step][:limit]

    samples: list[dict[str, Any]] = []
    for row in rows:
        samples.append(
            {
                "timestamp_unix": row.get("timestamp_unix"),
                "timestamp_utc": row.get("timestamp_utc"),
                "icmp_seq": int(row["icmp_seq"]) if str(row.get("icmp_seq", "")).isdigit() else None,
                "rtt_ms": _numeric(row.get("rtt_ms")),
            }
        )
    return samples, None


def _event(
    *,
    timestamp: str | None,
    relative_ms: float | None,
    source: str,
    category: str,
    event: str,
    node: str | None = None,
    details: str | None = None,
    confidence: str,
    raw: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "relative_ms": relative_ms,
        "source": source,
        "category": category,
        "event": event,
        "node": node,
        "details": _short(details),
        "confidence": confidence,
        "raw": _short(raw),
    }


def normalize_events(events: list[dict[str, str]], run_start: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    start_dt = _parse_iso(run_start)
    normalized: list[dict[str, Any]] = []
    for row in events:
        timestamp = row.get("timestamp")
        name = row.get("event") or "unknown"
        details = row.get("details")
        parsed_ts = _parse_iso(timestamp)
        relative_ms = None
        if parsed_ts and start_dt:
            relative_ms = round((parsed_ts - start_dt).total_seconds() * 1000, 3)
        elif timestamp:
            warnings.append(f"Could not parse event timestamp for {name}: {timestamp}")
        normalized.append(
            _event(
                timestamp=timestamp,
                relative_ms=relative_ms,
                source="events_csv",
                category=EVENT_CATEGORY.get(name, "unknown"),
                event=name,
                node=_node_from_details(details),
                details=details,
                confidence="observed",
                raw=f"{timestamp},{name},{details or ''}",
            )
        )
    return normalized, warnings


def _node_from_details(details: str | None) -> str | None:
    if not details:
        return None
    if "CU_telnet" in details:
        return "oai-cu"
    if "source gNB" in details:
        return "source_gnb"
    return None


def _log_node(path: Path) -> str:
    return path.stem


def _category_from_log(line: str) -> str:
    lower = line.lower()
    if "rrc" in lower:
        return "rrc"
    if "f1" in lower:
        return "f1"
    if "ngap" in lower or "n2" in lower:
        return "n2"
    if "ue" in lower:
        return "ue"
    if "handover" in lower or re.search(r"\bho\b", lower):
        return "trigger"
    return "unknown"


def _read_text_tail(path: Path, tail_bytes: int = 512 * 1024) -> tuple[list[str], str | None]:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > tail_bytes:
                handle.seek(size - tail_bytes)
                data = handle.read(tail_bytes)
                lines = data.decode(errors="replace").splitlines()
                return lines[1:] if lines else [], None
            data = handle.read()
            return data.decode(errors="replace").splitlines(), None
    except Exception as exc:
        return [], f"Could not read {path.name}: {exc}"


def _parse_log_events(
    run_dir: Path,
    limit_per_file: int = 30,
    tail_bytes: int = 512 * 1024,
) -> tuple[list[dict[str, Any]], list[str]]:
    logs_dir = run_dir / "docker_logs"
    if not logs_dir.exists():
        return [], []

    warnings: list[str] = []
    parsed: list[dict[str, Any]] = []
    patterns = re.compile(r"handover|ho\b|rrc|f1ap|ngap|reconfig|source gnb|target gnb", re.I)
    for path in sorted(logs_dir.glob("*.log")):
        lines, warning = _read_text_tail(path, tail_bytes=tail_bytes)
        if warning:
            warnings.append(warning)
            continue
        count = 0
        for line in lines:
            if not patterns.search(line):
                continue
            parsed.append(
                _event(
                    timestamp=None,
                    relative_ms=None,
                    source="docker_logs",
                    category=_category_from_log(line),
                    event="log_match",
                    node=_log_node(path),
                    details=_short(line),
                    confidence="parsed",
                    raw=line,
                )
            )
            count += 1
            if count >= limit_per_file:
                break
    return parsed, warnings


def _summary_from_artifacts(
    run_id: str,
    run_dir: Path,
    summary: dict[str, Any] | None,
    ping_summary: dict[str, Any] | None,
    iperf_summary: dict[str, Any] | None,
    event_count: int,
    warning_count: int,
) -> dict[str, Any]:
    base = summary or {}
    ping = ping_summary or {}
    iperf = iperf_summary or {}

    def pick(key: str) -> Any:
        if base.get(key) is not None:
            return base.get(key)
        if ping.get(key) is not None:
            return ping.get(key)
        if key.startswith("iperf_"):
            return iperf.get(key.removeprefix("iperf_"))
        return None

    start_time = base.get("start_time")
    end_time = base.get("end_time")
    return {
        "run_id": base.get("run_id") or run_id,
        "topology": base.get("topology"),
        "status": base.get("status"),
        "handover_triggered": base.get("handover_triggered"),
        "estimated_interruption_ms": pick("estimated_interruption_ms"),
        "first_ping_after_handover_ms": pick("first_ping_after_handover_ms"),
        "packet_loss_percent": pick("packet_loss_percent"),
        "rtt_min_ms": pick("rtt_min_ms"),
        "rtt_avg_ms": pick("rtt_avg_ms"),
        "rtt_max_ms": pick("rtt_max_ms"),
        "iperf_mbps": pick("iperf_mbps"),
        "iperf_jitter_ms": pick("iperf_jitter_ms"),
        "iperf_lost_percent": pick("iperf_lost_percent"),
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": _duration_seconds(start_time, end_time),
        "event_count": event_count,
        "warning_count": warning_count,
        "path": str(run_dir),
    }


def _handover_metric_events(summary: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if summary.get("estimated_interruption_ms") is not None:
        events.append(
            _event(
                timestamp=None,
                relative_ms=None,
                source="ping_summary",
                category="metric",
                event="estimated_interruption_ms",
                details=f"{summary['estimated_interruption_ms']} ms",
                confidence="inferred",
            )
        )
    return events


def _first_ping_event(trigger: dict[str, Any] | None, summary: dict[str, Any]) -> dict[str, Any] | None:
    first_ms = _numeric(summary.get("first_ping_after_handover_ms"))
    if first_ms is None:
        return None
    trigger_ts = _parse_iso((trigger or {}).get("timestamp"))
    ts = _iso(trigger_ts + timedelta(milliseconds=first_ms)) if trigger_ts else None
    trigger_relative = _numeric((trigger or {}).get("relative_ms"))
    relative_ms = round(trigger_relative + first_ms, 3) if trigger_relative is not None else None
    return _event(
        timestamp=ts,
        relative_ms=relative_ms,
        source="ping_summary",
        category="metric",
        event="first_ping_after_handover",
        details=f"{first_ms} ms after handover trigger",
        confidence="inferred",
    )


def message_flow_from_events(events: list[dict[str, Any]], topology: str | None = None) -> list[dict[str, Any]]:
    flow: list[dict[str, Any]] = []
    for event in events:
        name = event.get("event")
        if name in MESSAGE_FLOW_MAP:
            from_node, to_node = MESSAGE_FLOW_MAP[name]
        elif name in {"handover_trigger_start", "handover_trigger_end"}:
            if topology == "f1" or event.get("node") == "oai-cu":
                from_node, to_node = "Unknown", "CU"
            else:
                from_node, to_node = "Unknown", "Unknown"
        elif name in {"smoke_start", "before_handover", "after_handover", "smoke_end"}:
            from_node, to_node = "Unknown", "Unknown"
        else:
            continue
        flow.append(
            {
                "timestamp": event.get("timestamp"),
                "relative_ms": event.get("relative_ms"),
                "from": from_node,
                "to": to_node,
                "label": name,
                "source": event.get("source"),
                "confidence": event.get("confidence"),
                "details": event.get("details"),
            }
        )
    return flow


class HandoverEvents:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.runs_dir = repo_root / "results" / "runs"
        self._client = None

    def _docker(self):
        if docker is None:
            raise DockerException("Docker SDK is not installed")
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def runs(self) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.runs_dir.exists():
            return [], []
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        for run_dir in sorted((path for path in self.runs_dir.iterdir() if path.is_dir()), reverse=True):
            detail, detail_warnings = self.run_detail(run_dir.name, include_ping_samples=False, include_logs=False)
            if detail is None:
                warnings.extend(detail_warnings)
                continue
            summary = detail["summary"]
            summary["warning_count"] = len(detail_warnings)
            rows.append(summary)
            warnings.extend(f"{run_dir.name}: {warning}" for warning in detail_warnings if not warning.startswith("Missing optional"))
        return rows, warnings

    def durations(self) -> tuple[list[dict[str, Any]], list[str]]:
        return self.runs()

    def run_detail(
        self,
        run_id: str,
        *,
        include_ping_samples: bool = True,
        include_logs: bool = True,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        run_dir = self.runs_dir / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            return None, [f"Run not found: {run_id}"]

        warnings: list[str] = []
        summary_json, warning = _read_json(run_dir / "summary.json")
        if warning:
            warnings.append(warning)
        ping_summary, warning = _read_json(run_dir / "ping_summary.json")
        if warning:
            warnings.append(warning)
        iperf_summary, warning = _read_json(run_dir / "iperf_summary.json")
        if warning:
            warnings.append(warning)
        raw_events, warning = _read_events(run_dir / "events.csv")
        if warning:
            warnings.append(warning)
        events, event_warnings = normalize_events(raw_events, (summary_json or {}).get("start_time"))
        warnings.extend(event_warnings)

        normalized_summary = _summary_from_artifacts(
            run_id,
            run_dir,
            summary_json,
            ping_summary,
            iperf_summary,
            event_count=len(events),
            warning_count=len(warnings),
        )
        trigger = next((event for event in events if event.get("event") == "handover_trigger_start"), None)
        first_ping = _first_ping_event(trigger, normalized_summary)
        if first_ping:
            events.append(first_ping)
        events.extend(_handover_metric_events(normalized_summary))

        if include_logs:
            log_events, log_warnings = _parse_log_events(run_dir)
            events.extend(log_events)
            warnings.extend(log_warnings)

        ping_samples: list[dict[str, Any]] = []
        if include_ping_samples:
            ping_samples, warning = _read_ping_samples(run_dir / "ping.csv")
            if warning:
                warnings.append(warning)

        flow = message_flow_from_events(events, normalized_summary.get("topology"))
        return {
            "run_id": run_id,
            "summary": normalized_summary | {"warning_count": len(warnings), "event_count": len(events)},
            "events": events,
            "message_flow": flow,
            "ping_interruption_markers": {
                "handover_trigger_start": trigger,
                "first_ping_after_handover": first_ping,
            },
            "ping_samples": ping_samples,
            "warnings": warnings,
        }, warnings

    def message_flow(self, run_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        detail, warnings = self.run_detail(run_id, include_ping_samples=False, include_logs=True)
        if detail is None:
            return [], warnings
        return detail["message_flow"], warnings

    def live_status(
        self,
        topology: TopologyConfig,
        containers: list[dict[str, Any]],
        telnet: dict[str, Any],
        recent_events: Any = _UNSET,
    ) -> dict[str, Any]:
        """Current mobility readiness plus recent log-derived events. ``recent_events``
        may be supplied by a caller that already collected them on a slower refresh
        tier; when omitted they are read inline (the original behavior)."""
        warnings: list[str] = []
        telnet_status = telnet_observation(telnet.get("cu") or {})
        cu_telnet_reachable = telnet_status == "reachable"
        required_missing = any(item.get("required") and item.get("status") != "running" for item in containers)
        if required_missing:
            readiness = "unavailable"
        elif cu_telnet_reachable:
            readiness = "ready"
        elif telnet_status in {"polling_disabled", "no_endpoint"}:
            # Nothing probed the control node, so nothing is claimed about it. This is
            # the default configuration (passive polling is off for OAI CU stability) and
            # a structural fact for topologies with no telnet node — neither is a fault,
            # and neither should read as a degraded stack.
            readiness = "not_observed"
        else:
            readiness = "degraded"
            warnings.append("CU/source telnet was probed and is not reachable; live handover context is limited.")

        if recent_events is _UNSET:
            recent_events, log_warnings = self.collect_live_log_events(topology)
            warnings.extend(log_warnings)
        return {
            "topology": topology.name,
            "handover_type": topology.handover_type,
            "readiness": readiness,
            "cu_telnet_reachable": cu_telnet_reachable,
            "cu_telnet_status": telnet_status,
            "known_source_du": None,
            "known_target_du": None,
            "last_handover_event": recent_events[-1] if recent_events else None,
            "recent_events": recent_events[-20:],
            "warnings": warnings,
        }

    def collect_live_log_events(self, topology: TopologyConfig) -> tuple[list[dict[str, Any]], list[str]]:
        """Public entry point for bounded live log scraping. Blocking (reads Docker
        logs); the snapshot collector calls it on its own refresh tier."""
        return self._live_log_events(topology)

    def _live_log_events(self, topology: TopologyConfig) -> tuple[list[dict[str, Any]], list[str]]:
        names = [node.container for node in topology.nodes if node.role in {"cu", "du", "gnb", "ue"}]
        warnings: list[str] = []
        events: list[dict[str, Any]] = []
        try:
            client = self._docker()
            client.ping()
        except DockerException as exc:
            return [], [f"Docker API unavailable for live handover logs: {exc}"]

        pattern = re.compile(r"handover|ho\b|rrc|f1ap|ngap|reconfig", re.I)
        for name in names:
            try:
                container = client.containers.get(name)
                if container.status != "running":
                    continue
                logs = container.logs(tail=200).decode(errors="replace")
            except NotFound:
                continue
            except DockerException as exc:
                warnings.append(f"Could not read live logs for {name}: {exc}")
                continue
            for line in logs.splitlines()[-200:]:
                if not pattern.search(line):
                    continue
                events.append(
                    _event(
                        timestamp=None,
                        relative_ms=None,
                        source="docker_logs",
                        category=_category_from_log(line),
                        event="log_match",
                        node=name,
                        details=_short(line),
                        confidence="parsed",
                        raw=line,
                    )
                )
        return events[-20:], warnings
