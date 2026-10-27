from __future__ import annotations

import re
from typing import Any

from config import TopologyConfig

from collectors.handover_events import DockerException, HandoverEvents, NotFound

# Distinguishes "caller supplied nothing" from "caller supplied None", since None is
# itself a valid collected value for both live mobility and the handover chart.
_UNSET = object()


def _status(container_name: str, containers: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in containers if item.get("name") == container_name), None)


def _metric_summary(latest_run: dict[str, Any] | None) -> dict[str, Any]:
    latest = latest_run or {}
    return {
        "estimated_interruption_ms": latest.get("estimated_interruption_ms"),
        "first_ping_after_handover_ms": latest.get("first_ping_after_handover_ms"),
        "packet_loss_percent": latest.get("packet_loss_percent"),
        "rtt_min_ms": latest.get("rtt_min_ms"),
        "rtt_avg_ms": latest.get("rtt_avg_ms"),
        "rtt_max_ms": latest.get("rtt_max_ms"),
        "iperf_mbps": latest.get("iperf_mbps"),
        "iperf_jitter_ms": latest.get("iperf_jitter_ms"),
        "iperf_lost_percent": latest.get("iperf_lost_percent"),
    }


def _known_f1_path(serving_du: str | None) -> list[str]:
    du = serving_du if serving_du in {"DU0", "DU1"} else "Unknown"
    return ["UE", du, "CU", "UPF", "EXT-DN"]


def _du_from_attached_ue(ue: dict[str, Any]) -> str | None:
    raw = ue.get("serving_du") or ue.get("du") or ue.get("du_id")
    if raw is None:
        return None
    normalized = str(raw).upper().replace("OAI-", "")
    if normalized in {"DU0", "0"}:
        return "DU0"
    if normalized in {"DU1", "1"}:
        return "DU1"
    return str(raw)


def _cell_hex(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{int(value):x}"
    except (TypeError, ValueError):
        text = str(value).lower().removeprefix("0x")
        return text or None


def _du_maps(config: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    by_cell: dict[str, str] = {}
    by_ip: dict[str, str] = {}
    for du in config.get("dus") or []:
        name = du.get("name")
        if name not in {"DU0", "DU1"}:
            continue
        cell = _cell_hex(du.get("nr_cellid"))
        if cell:
            by_cell[cell] = name
            by_cell[str(du.get("nr_cellid"))] = name
        if du.get("f1_local_address"):
            by_ip[str(du["f1_local_address"])] = name
    return by_cell, by_ip


def _ue_id_from_config(config: dict[str, Any]) -> str:
    imsi = (config.get("ue") or {}).get("imsi")
    return f"imsi-{imsi}" if imsi else "RFsim UE"


class OperatorOverview:
    def __init__(self, handover_events: HandoverEvents) -> None:
        self.handover_events = handover_events

    def collect_live_mobility(
        self, topology: TopologyConfig, config: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Public entry point for the log-derived mobility state. Blocking (reads
        Docker logs); the snapshot collector calls it on its own refresh tier."""
        return self._live_mobility_from_logs(topology, config)

    def collect_handover_chart(
        self, latest_run: dict[str, Any] | None
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Public entry point for the latest-run chart. Blocking (reads run artifacts)."""
        return self._latest_handover_chart(latest_run)

    def build(
        self,
        *,
        topology: TopologyConfig,
        containers: list[dict[str, Any]],
        config: dict[str, Any],
        live_kpis: dict[str, Any],
        latest_run: dict[str, Any] | None,
        handover: dict[str, Any],
        actions: dict[str, Any],
        live_latency: dict[str, Any] | None = None,
        live_mobility: Any = _UNSET,
        handover_chart: Any = _UNSET,
    ) -> tuple[dict[str, Any], list[str]]:
        """Assemble the operator overview. ``live_mobility`` and ``handover_chart``
        may be supplied by a caller that already collected them on a slower refresh
        tier; when omitted they are collected inline (the original behavior)."""
        warnings: list[str] = []
        if live_mobility is _UNSET:
            live_mobility, mobility_warnings = self.collect_live_mobility(topology, config)
            warnings.extend(mobility_warnings)
        if handover_chart is _UNSET:
            chart, chart_warnings = self.collect_handover_chart(latest_run)
            warnings.extend(chart_warnings)
        else:
            chart = handover_chart
        return {
            "topology": topology.name,
            "radio_mode": topology.radio_mode,
            "handover_type": topology.handover_type,
            "ue_paths": self._ue_paths(
                topology=topology,
                containers=containers,
                config=config,
                live_kpis=live_kpis,
                latest_run=latest_run,
                live_mobility=live_mobility,
            ),
            "latest_metrics": _metric_summary(latest_run),
            "handover_chart": chart,
            "live_latency": live_latency,
            "actions": {
                "enabled": actions.get("enabled"),
                "running_job": actions.get("running_job"),
                "trigger_supported": topology.name == "f1" and topology.handover_type == "f1",
            },
            "handover": {
                "readiness": handover.get("readiness"),
                "last_handover_event": handover.get("last_handover_event"),
                "known_source_du": handover.get("known_source_du"),
                "known_target_du": handover.get("known_target_du"),
                "live_mobility": live_mobility,
            },
            "warnings": warnings,
        }, warnings

    def _ue_paths(
        self,
        *,
        topology: TopologyConfig,
        containers: list[dict[str, Any]],
        config: dict[str, Any],
        live_kpis: dict[str, Any],
        latest_run: dict[str, Any] | None,
        live_mobility: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        attached = live_kpis.get("attached_ues") or []
        metrics = _metric_summary(latest_run)
        log_serving_du = (live_mobility or {}).get("serving_du")
        log_rnti = (live_mobility or {}).get("rnti")
        if attached:
            rows = []
            for index, ue in enumerate(attached, start=1):
                serving_du = _du_from_attached_ue(ue) or log_serving_du
                rows.append(
                    {
                        "ue_id": ue.get("imsi") or ue.get("supi") or ue.get("rnti") or f"UE {index}",
                        "serving_du": serving_du,
                        "path": _known_f1_path(serving_du) if topology.name == "f1" else ["UE", "Unknown"],
                        "metrics": metrics,
                        "source": "cu_telnet" if _du_from_attached_ue(ue) else "cu_logs_tail",
                        "confidence": "observed" if _du_from_attached_ue(ue) else "parsed",
                        "raw": ue,
                        "warnings": [] if serving_du else ["Serving DU was not exposed by current UE telemetry."],
                    }
                )
            return rows

        ue_container = _status("oai-nr-ue", containers)
        if log_serving_du:
            return [
                {
                    "ue_id": _ue_id_from_config(config),
                    "serving_du": log_serving_du,
                    "path": _known_f1_path(log_serving_du) if topology.name == "f1" else ["UE", log_serving_du],
                    "metrics": metrics,
                    "source": "cu_logs_tail",
                    "confidence": "parsed",
                    "raw": live_mobility,
                    "rnti": log_rnti,
                    "warnings": [],
                }
            ]

        if latest_run:
            return [
                {
                    "ue_id": _ue_id_from_config(config),
                    "serving_du": None,
                    "path": _known_f1_path(None) if topology.name == "f1" else ["UE", "Unknown"],
                    "metrics": metrics,
                    "source": "latest_run_artifacts",
                    "confidence": "inferred",
                    "raw": None,
                    "warnings": [
                        "Current serving DU is unavailable; metrics are inferred from the latest run artifact.",
                    ],
                }
            ]

        if ue_container and ue_container.get("status") == "running":
            return [
                {
                    "ue_id": _ue_id_from_config(config),
                    "serving_du": None,
                    "path": _known_f1_path(None) if topology.name == "f1" else ["UE", "Unknown"],
                    "metrics": metrics,
                    "source": "container_status",
                    "confidence": "unknown",
                    "raw": None,
                    "warnings": ["UE container is running, but no current UE context or run metrics are available."],
                }
            ]
        return []

    def _live_mobility_from_logs(self, topology: TopologyConfig, config: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        if topology.name != "f1":
            return None, []
        by_cell, by_ip = _du_maps(config)
        warnings: list[str] = []
        try:
            client = self.handover_events._docker()  # noqa: SLF001 - share existing Docker client/cache
            container = client.containers.get("oai-cu")
            if container.status != "running":
                return None, []
            lines = container.logs(tail=600).decode(errors="replace").splitlines()
        except NotFound:
            # The container does not exist (nothing deployed, or a different topology).
            # Nothing to read is not a failure to read.
            return None, []
        except DockerException as exc:
            return None, [f"Could not read CU logs for live mobility state: {exc}"]

        trigger_re = re.compile(
            r"(?P<seconds>\d+\.\d+).*Handover triggered for UE (?P<ue>\d+)/RNTI (?P<rnti>[0-9a-fA-F]+) "
            r"towards cell (?P<cell>[0-9a-fA-F]+)/assoc_id (?P<assoc>\d+)/PCI (?P<pci>\d+)",
            re.I,
        )
        complete_cell_re = re.compile(
            r"(?P<seconds>\d+\.\d+).*cellID (?P<cell>[0-9a-fA-F]+), UE ID (?P<ue>\d+) RNTI (?P<rnti>[0-9a-fA-F]+).*Received RRCReconfigurationComplete",
            re.I,
        )
        complete_re = re.compile(r"(?P<seconds>\d+\.\d+).*handover for UE (?P<ue>\d+)/RNTI (?P<rnti>[0-9a-fA-F]+) complete", re.I)
        gtpu_re = re.compile(r"Update tunnel .* remote IPv4 (?P<ip>\d+\.\d+\.\d+\.\d+)", re.I)

        last_trigger: dict[str, Any] | None = None
        last_complete_cell_by_rnti: dict[str, dict[str, Any]] = {}
        last_complete: dict[str, Any] | None = None
        recent_handover_durations: list[dict[str, Any]] = []
        last_gtpu_du: str | None = None
        for line in lines:
            if match := trigger_re.search(line):
                cell = match.group("cell").lower()
                last_trigger = {
                    "seconds": float(match.group("seconds")),
                    "ue_id": match.group("ue"),
                    "rnti": match.group("rnti"),
                    "target_cell": cell,
                    "target_du": by_cell.get(cell),
                    "target_pci": int(match.group("pci")),
                    "raw": line[-240:],
                }
            if match := complete_cell_re.search(line):
                cell = match.group("cell").lower()
                last_complete_cell_by_rnti[match.group("rnti").lower()] = {
                    "seconds": float(match.group("seconds")),
                    "ue_id": match.group("ue"),
                    "rnti": match.group("rnti"),
                    "cell": cell,
                    "serving_du": by_cell.get(cell),
                    "raw": line[-240:],
                }
            if match := gtpu_re.search(line):
                last_gtpu_du = by_ip.get(match.group("ip"))
            if match := complete_re.search(line):
                rnti = match.group("rnti").lower()
                complete_cell = last_complete_cell_by_rnti.get(rnti, {})
                seconds = float(match.group("seconds"))
                duration_ms = None
                if last_trigger and last_trigger.get("ue_id") == match.group("ue"):
                    duration_ms = round((seconds - float(last_trigger["seconds"])) * 1000, 3)
                last_complete = {
                    "seconds": seconds,
                    "ue_id": match.group("ue"),
                    "rnti": match.group("rnti"),
                    "serving_du": complete_cell.get("serving_du") or last_gtpu_du,
                    "cell": complete_cell.get("cell"),
                    "last_trigger": last_trigger,
                    "last_handover_duration_ms": duration_ms,
                    "source": "cu_logs_tail",
                    "confidence": "parsed",
                    "raw": line[-240:],
                }
                if duration_ms is not None:
                    recent_handover_durations.append(
                        {
                            "label": f"HO {len(recent_handover_durations) + 1}",
                            "seconds": seconds,
                            "duration_ms": duration_ms,
                            "serving_du": last_complete.get("serving_du"),
                            "rnti": last_complete.get("rnti"),
                        }
                    )

        if last_complete:
            last_complete["recent_handover_durations"] = recent_handover_durations[-20:]
            return last_complete, warnings
        if last_gtpu_du:
            return {
                "serving_du": last_gtpu_du,
                "source": "cu_logs_tail",
                "confidence": "parsed",
                "warnings": ["Serving DU inferred from latest CU GTP-U tunnel update."],
            }, warnings
        return None, warnings

    def _latest_handover_chart(self, latest_run: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
        run_id = (latest_run or {}).get("run_id")
        warnings: list[str] = []
        if not run_id:
            runs, run_warnings = self.handover_events.runs()
            warnings.extend(run_warnings)
            run_id = next((row.get("run_id") for row in runs if row.get("handover_triggered") is True), None)
        if not run_id:
            return None, warnings

        detail, detail_warnings = self.handover_events.run_detail(str(run_id), include_ping_samples=True, include_logs=False)
        warnings.extend(warning for warning in detail_warnings if not warning.startswith("Missing optional"))
        if detail is None:
            return None, warnings

        samples = detail.get("ping_samples") or []
        if len(samples) > 240:
            step = max(1, len(samples) // 240)
            samples = samples[::step][:240]
        return {
            "run_id": detail.get("run_id"),
            "summary": detail.get("summary"),
            "ping_samples": samples,
            "markers": detail.get("ping_interruption_markers") or {},
            "warnings": warnings,
        }, warnings
