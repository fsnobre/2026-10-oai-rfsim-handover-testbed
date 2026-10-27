from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.handover_events import HandoverEvents
from collectors.live_latency import parse_ping_rtt
from collectors.operator_overview import OperatorOverview, _du_maps
from config import TOPOLOGIES


def _write_run(root: Path) -> dict[str, object]:
    run_dir = root / "results" / "runs" / "20260701_084915_f1_handover_smoke"
    run_dir.mkdir(parents=True)
    summary = {
        "run_id": run_dir.name,
        "topology": "f1",
        "status": "pass",
        "handover_triggered": True,
        "estimated_interruption_ms": 200.924,
        "first_ping_after_handover_ms": 80.0,
        "packet_loss_percent": 0.0,
        "rtt_min_ms": 8.0,
        "rtt_avg_ms": 12.1,
        "rtt_max_ms": 25.0,
        "iperf_mbps": 10.5,
        "start_time": "2026-07-01T11:49:15Z",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary))
    (run_dir / "ping_summary.json").write_text(json.dumps(summary))
    with (run_dir / "events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "event", "details"])
        writer.writeheader()
        writer.writerow({"timestamp": "2026-07-01T11:50:12Z", "event": "handover_trigger_start", "details": "test"})
    with (run_dir / "ping.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp_unix", "timestamp_utc", "icmp_seq", "rtt_ms"])
        writer.writeheader()
        writer.writerow({"timestamp_unix": "1", "timestamp_utc": "2026-07-01T11:50:11Z", "icmp_seq": "1", "rtt_ms": "10.0"})
        writer.writerow({"timestamp_unix": "2", "timestamp_utc": "2026-07-01T11:50:12Z", "icmp_seq": "2", "rtt_ms": "20.0"})
    return summary


def _base_state(root: Path) -> tuple[OperatorOverview, dict[str, object]]:
    handover = HandoverEvents(root)
    overview = OperatorOverview(handover)
    config = {"ue": {"imsi": "001010000000001"}}
    common = {
        "topology": TOPOLOGIES["f1"],
        "containers": [{"name": "oai-nr-ue", "status": "running", "role": "ue"}],
        "config": config,
        "handover": {"readiness": "ready"},
        "actions": {"enabled": False, "running_job": None},
    }
    return overview, common


def validate_empty_repo() -> None:
    with TemporaryDirectory() as tmp:
        overview, common = _base_state(Path(tmp))
        data, warnings = overview.build(live_kpis={"attached_ues": []}, latest_run=None, **common)
        assert data["handover_chart"] is None
        assert data["ue_paths"][0]["confidence"] == "unknown"
        assert isinstance(warnings, list)


def validate_latest_run_chart_and_inferred_path() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        latest = _write_run(root)
        overview, common = _base_state(root)
        data, _warnings = overview.build(live_kpis={"attached_ues": []}, latest_run=latest, **common)
        assert data["ue_paths"][0]["ue_id"] == "imsi-001010000000001"
        assert data["ue_paths"][0]["confidence"] == "inferred"
        assert data["ue_paths"][0]["metrics"]["estimated_interruption_ms"] == 200.924
        assert data["handover_chart"]["run_id"] == latest["run_id"]
        assert len(data["handover_chart"]["ping_samples"]) == 2
        assert data["handover_chart"]["markers"]["handover_trigger_start"]["event"] == "handover_trigger_start"


def validate_live_attached_ue_path() -> None:
    with TemporaryDirectory() as tmp:
        overview, common = _base_state(Path(tmp))
        data, _warnings = overview.build(
            live_kpis={"attached_ues": [{"rnti": "0x1234", "serving_du": "DU1"}]},
            latest_run=None,
            **common,
        )
        assert data["ue_paths"][0]["confidence"] == "observed"
        assert data["ue_paths"][0]["serving_du"] == "DU1"
        assert data["ue_paths"][0]["path"] == ["UE", "DU1", "CU", "UPF", "EXT-DN"]


def validate_du_maps() -> None:
    by_cell, by_ip = _du_maps(
        {
            "dus": [
                {"name": "DU0", "nr_cellid": 12345678, "f1_local_address": "192.168.70.171"},
                {"name": "DU1", "nr_cellid": 11111111, "f1_local_address": "192.168.70.172"},
            ]
        }
    )
    assert by_cell["bc614e"] == "DU0"
    assert by_cell["a98ac7"] == "DU1"
    assert by_ip["192.168.70.171"] == "DU0"
    assert by_ip["192.168.70.172"] == "DU1"


def validate_live_latency_parser() -> None:
    assert parse_ping_rtt("64 bytes from 192.168.71.135: icmp_seq=1 ttl=64 time=8.42 ms") == 8.42
    assert parse_ping_rtt("rtt min/avg/max/mdev = 8.421/8.421/8.421/0.000 ms") is None
    assert parse_ping_rtt("Destination Host Unreachable") is None


def main() -> int:
    validate_empty_repo()
    validate_latest_run_chart_and_inferred_path()
    validate_live_attached_ue_path()
    validate_du_maps()
    validate_live_latency_parser()
    print("Phase 6 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
