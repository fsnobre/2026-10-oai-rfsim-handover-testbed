from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import actions
from actions import (
    REPEATED_SMOKE_MAX_COUNT,
    ActionError,
    ActionManager,
    build_repeated_smoke_test_command,
)
from collectors.campaigns import Campaigns, _resolve_run_dir, statistics_for_rows


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_id",
        "status",
        "packet_loss_percent",
        "rtt_avg_ms",
        "estimated_interruption_ms",
        "first_ping_after_handover_ms",
        "iperf_mbps",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _make_run(root: Path, run_id: str, summary: dict[str, object]) -> Path:
    run_dir = root / "results" / "runs" / run_id
    _write_json(run_dir / "summary.json", {"run_id": run_id, **summary})
    return run_dir


def test_empty_results() -> None:
    with TemporaryDirectory() as tmp:
        collector = Campaigns(Path(tmp))
        campaigns, warnings = collector.list_campaigns()
        assert campaigns == []
        assert warnings == []
        rows, warnings = collector.export_rows()
        assert rows == []
        assert warnings == []


def test_campaign_summary_and_outliers() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run1 = _make_run(
            root,
            "run-pass-a",
            {
                "topology": "f1",
                "status": "pass",
                "handover_triggered": True,
                "estimated_interruption_ms": 100,
                "first_ping_after_handover_ms": 80,
                "packet_loss_percent": 1,
                "rtt_avg_ms": 10,
                "iperf_mbps": 5,
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:01:00Z",
            },
        )
        run2 = _make_run(
            root,
            "run-fail-b",
            {
                "topology": "f1",
                "status": "failed",
                "handover_triggered": False,
                "estimated_interruption_ms": 300,
                "first_ping_after_handover_ms": 250,
                "packet_loss_percent": 5,
                "rtt_avg_ms": 30,
                "iperf_mbps": 2,
                "start_time": "2026-01-01T00:02:00Z",
                "end_time": "2026-01-01T00:03:00Z",
            },
        )
        run3 = _make_run(
            root,
            "run-pass-c",
            {
                "topology": "f1",
                "status": "pass",
                "handover_triggered": True,
                "estimated_interruption_ms": None,
                "packet_loss_percent": None,
                "rtt_avg_ms": 20,
                "iperf_mbps": None,
                "start_time": "2026-01-01T00:04:00Z",
                "end_time": "2026-01-01T00:05:00Z",
            },
        )
        campaign_dir = root / "results" / "repeated" / "20260101_f1_repeated"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "runs.txt").write_text(f"{run1}\n{run2}\n{run3}\n")
        _write_json(
            campaign_dir / "summary.json",
            {"repeat_id": campaign_dir.name, "requested_runs": 3, "runs": [str(run1), str(run2), str(run3)]},
        )
        _write_csv(
            campaign_dir / "summary.csv",
            [
                {"run_id": "run-pass-a", "status": "pass"},
                {"run_id": "run-fail-b", "status": "failed"},
                {"run_id": "run-pass-c", "status": "pass"},
            ],
        )

        collector = Campaigns(root)
        detail, warnings = collector.get_campaign(campaign_dir.name)
        assert detail is not None
        assert warnings == []
        summary = detail["summary"]
        assert summary["run_count"] == 3
        assert summary["passed_count"] == 2
        assert summary["failed_count"] == 1
        assert summary["pass_rate_percent"] == 66.667
        assert summary["handover_triggered_count"] == 2
        assert summary["statistics"]["estimated_interruption_ms"]["mean"] == 200.0
        assert summary["statistics"]["estimated_interruption_ms"]["median"] == 200.0
        assert summary["statistics"]["estimated_interruption_ms"]["p95"] == 300.0
        assert detail["outliers"]["failed_runs"][0]["run_id"] == "run-fail-b"
        assert detail["outliers"]["missing_handover_trigger"][0]["run_id"] == "run-fail-b"
        assert detail["outliers"]["missing_ping_metrics"][0]["run_id"] == "run-pass-c"
        assert detail["outliers"]["highest_interruption"][0]["run_id"] == "run-fail-b"
        assert detail["outliers"]["lowest_iperf_mbps"][0]["run_id"] == "run-fail-b"


def test_statistics_ignore_nulls_and_are_deterministic() -> None:
    rows = [
        {"estimated_interruption_ms": None},
        {"estimated_interruption_ms": 10},
        {"estimated_interruption_ms": 20},
        {"estimated_interruption_ms": 30},
        {"estimated_interruption_ms": 40},
    ]
    stats = statistics_for_rows(rows)["estimated_interruption_ms"]
    assert stats["count"] == 4
    assert stats["median"] == 25.0
    assert stats["p95"] == 40.0


def test_host_absolute_run_path_remaps_to_repo_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "20260601_120000_f1_handover_smoke"
        run = _make_run(
            root,
            run_id,
            {
                "topology": "f1",
                "status": "pass",
                "handover_triggered": True,
                "estimated_interruption_ms": 123.456,
                "packet_loss_percent": 0.5,
                "rtt_avg_ms": 12.25,
            },
        )
        fake_host_path = Path("/home/nobre/Documents/repos/oai-rfsim-handover-testbed/results/runs") / run.name
        campaign_dir = root / "results" / "repeated" / "20260601_f1_repeated"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "runs.txt").write_text(f"{fake_host_path}\n")

        resolved = _resolve_run_dir(root, str(fake_host_path))
        assert resolved == run

        detail, warnings = Campaigns(root).get_campaign(campaign_dir.name)
        assert detail is not None
        assert not any("Missing optional artifact: summary.json" in warning for warning in warnings)
        assert detail["runs"][0]["run_id"] == run_id
        assert detail["runs"][0]["estimated_interruption_ms"] == 123.456
        assert detail["runs"][0]["packet_loss_percent"] == 0.5
        assert detail["runs"][0]["rtt_avg_ms"] == 12.25


def test_malformed_artifacts_warn() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        campaign_dir = root / "results" / "repeated" / "bad_f1_repeated"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "summary.json").write_text("{not-json")
        (campaign_dir / "summary.csv").write_text("")
        detail, warnings = Campaigns(root).get_campaign(campaign_dir.name)
        assert detail is not None
        assert any("Could not parse summary.json" in warning for warning in warnings)
        assert any("Could not parse summary.csv" in warning for warning in warnings)


def test_export_rows() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run = _make_run(root, "run-a", {"topology": "n2-cu-du", "status": "pass"})
        campaign_dir = root / "results" / "repeated" / "20260101_n2_cu_du_repeated"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "runs.txt").write_text(f"{run}\n")
        rows, warnings = Campaigns(root).export_rows()
        assert warnings == []
        assert rows == [{"campaign_id": campaign_dir.name, **rows[0]}]
        assert rows[0]["campaign_id"] == campaign_dir.name
        assert rows[0]["run_id"] == "run-a"


async def test_repeated_action_guards() -> None:
    root = Path("/repo")
    command = build_repeated_smoke_test_command(root, "f1", 5, 3600)
    assert command.argv == ["bash", "/repo/scripts/run_repeated_smoke_tests.sh", "f1"]
    assert command.env == {"RUNS": "5"}

    for bad_count in (0, REPEATED_SMOKE_MAX_COUNT + 1):
        try:
            build_repeated_smoke_test_command(root, "f1", bad_count, 3600)
        except ActionError as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("bad repeated count was not rejected")

    try:
        build_repeated_smoke_test_command(root, "bad-topology", 1, 3600)
    except ActionError as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("bad repeated topology was not rejected")

    manager = ActionManager(
        root,
        actions_enabled=False,
        trigger_timeout_seconds=1,
        measure_interruption_timeout_seconds=1,
        smoke_timeout_seconds=1,
        repeated_smoke_timeout_seconds=1,
    )
    try:
        await manager.start_repeated_smoke_test(confirm=True, topology="f1", count=1)
    except ActionError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("disabled repeated action was not rejected")

    manager_enabled = ActionManager(
        root,
        actions_enabled=True,
        trigger_timeout_seconds=1,
        measure_interruption_timeout_seconds=1,
        smoke_timeout_seconds=1,
        repeated_smoke_timeout_seconds=1,
    )
    try:
        await manager_enabled.start_repeated_smoke_test(confirm=False, topology="f1", count=1)
    except ActionError as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("missing confirm was not rejected")

    source = Path(actions.__file__).read_text()
    assert "shell=True" not in source
    assert "create_subprocess_shell" not in source


def main() -> int:
    test_empty_results()
    test_campaign_summary_and_outliers()
    test_statistics_ignore_nulls_and_are_deterministic()
    test_host_absolute_run_path_remaps_to_repo_root()
    test_malformed_artifacts_warn()
    test_export_rows()
    asyncio.run(test_repeated_action_guards())
    print("Phase 5 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
