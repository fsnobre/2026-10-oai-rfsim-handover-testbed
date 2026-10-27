from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.handover_events import HandoverEvents, _read_text_tail, message_flow_from_events, normalize_events
from config import TopologyConfig


def _collector(root: Path) -> HandoverEvents:
    return HandoverEvents(root)


def validate_missing_runs() -> None:
    with TemporaryDirectory() as tmp:
        runs, warnings = _collector(Path(tmp)).runs()
        assert runs == []
        assert warnings == []


def validate_partial_summary_only() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "results" / "runs" / "20260101_000000_f1_handover_smoke"
        run.mkdir(parents=True)
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": run.name,
                    "topology": "f1",
                    "status": "failed",
                    "handover_triggered": False,
                    "start_time": "2026-01-01T00:00:00Z",
                    "end_time": "2026-01-01T00:00:05Z",
                }
            )
        )
        detail, warnings = _collector(root).run_detail(run.name)
        assert detail is not None
        assert detail["summary"]["duration_seconds"] == 5
        assert detail["events"] == []
        assert detail["message_flow"] == []
        assert any("events.csv" in warning for warning in warnings)


def validate_events_and_message_flow() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "results" / "runs" / "20260101_000001_f1_handover_smoke"
        run.mkdir(parents=True)
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": run.name,
                    "topology": "f1",
                    "status": "pass",
                    "handover_triggered": True,
                    "start_time": "2026-01-01T00:00:00Z",
                    "end_time": "2026-01-01T00:00:10Z",
                    "estimated_interruption_ms": 200.0,
                    "first_ping_after_handover_ms": 50.0,
                }
            )
        )
        (run / "events.csv").write_text(
            "timestamp,event,details\n"
            "2026-01-01T00:00:00Z,smoke_start,run_id=x topology=f1\n"
            "2026-01-01T00:00:01Z,ping_capture_start,target=192.168.71.135\n"
            "2026-01-01T00:00:03Z,handover_trigger_start,CU_telnet 192.168.70.150:9090\n"
            "2026-01-01T00:00:03Z,handover_trigger_end,command=ci trigger_f1_ho\n"
            "2026-01-01T00:00:08Z,ping_capture_stop,pid=1\n"
            "2026-01-01T00:00:10Z,smoke_end,status=pass\n"
        )
        detail, warnings = _collector(root).run_detail(run.name)
        assert detail is not None
        assert detail["summary"]["event_count"] >= 6
        assert detail["summary"]["estimated_interruption_ms"] == 200.0
        assert any(step["label"] == "handover_trigger_start" for step in detail["message_flow"])
        assert any(step["label"] == "first_ping_after_handover" for step in detail["message_flow"])
        assert detail["ping_interruption_markers"]["first_ping_after_handover"]["timestamp"] == "2026-01-01T00:00:03.050000Z"
        assert warnings


def validate_sparse_message_flow_unknowns() -> None:
    events, warnings = normalize_events(
        [{"timestamp": "2026-01-01T00:00:00Z", "event": "handover_trigger_start", "details": "opaque"}],
        "2026-01-01T00:00:00Z",
    )
    assert warnings == []
    flow = message_flow_from_events(events, topology="n2-cu-du")
    assert flow[0]["from"] == "Unknown"
    assert flow[0]["to"] == "Unknown"


def validate_live_status_does_not_fabricate_du() -> None:
    topology = TopologyConfig(
        name="f1",
        radio_mode="rfsim",
        handover_type="f1",
        ran_compose="gnb-docker-compose.yaml",
        compose_files=(),
        experiment_config="",
        nodes=(),
    )
    status = HandoverEvents(Path("/tmp/nonexistent")).live_status(
        topology,
        containers=[],
        telnet={"cu": {"reachable": False}},
    )
    assert status["known_source_du"] is None
    assert status["known_target_du"] is None


def validate_duration_table() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "results" / "runs" / "20260101_000002_n2_cu_du_smoke"
        run.mkdir(parents=True)
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": run.name,
                    "topology": "n2-cu-du",
                    "status": "pass",
                    "handover_triggered": True,
                    "start_time": "2026-01-01T00:00:00Z",
                    "end_time": "2026-01-01T00:00:20Z",
                    "estimated_interruption_ms": 123.0,
                }
            )
        )
        rows, warnings = _collector(root).durations()
        assert len(rows) == 1
        assert rows[0]["duration_seconds"] == 20
        assert rows[0]["estimated_interruption_ms"] == 123.0
        assert warnings == []


def validate_bounded_artifact_log_tail() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "results" / "runs" / "20260101_000004_large_log"
        logs = run / "docker_logs"
        logs.mkdir(parents=True)
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": run.name,
                    "topology": "f1",
                    "status": "pass",
                    "handover_triggered": True,
                }
            )
        )
        (run / "events.csv").write_text("timestamp,event,details\n")
        log_path = logs / "oai-cu.log"
        log_path.write_text(("irrelevant startup line\n" * 40000) + "F1AP handover RRC reconfiguration complete\n")

        tail_lines, warning = _read_text_tail(log_path, tail_bytes=512 * 1024)
        assert warning is None
        assert len(tail_lines) < 40000
        assert tail_lines[-1] == "F1AP handover RRC reconfiguration complete"

        detail, warnings = _collector(root).run_detail(run.name)
        assert detail is not None
        assert any(event["source"] == "docker_logs" and "F1AP handover" in event["details"] for event in detail["events"])
        assert not any("oai-cu.log" in warning for warning in warnings)


def validate_malformed_artifacts_warn() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = root / "results" / "runs" / "20260101_000003_bad"
        run.mkdir(parents=True)
        (run / "summary.json").write_text("{bad json")
        (run / "events.csv").write_text("not,the,right,columns\n1,2,3,4\n")
        detail, warnings = _collector(root).run_detail(run.name)
        assert detail is not None
        assert any("summary.json" in warning for warning in warnings)
        assert any("events.csv" in warning for warning in warnings)


def main() -> int:
    validate_missing_runs()
    validate_partial_summary_only()
    validate_events_and_message_flow()
    validate_sparse_message_flow_unknowns()
    validate_live_status_does_not_fabricate_du()
    validate_duration_table()
    validate_bounded_artifact_log_tail()
    validate_malformed_artifacts_warn()
    print("Phase 3 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
