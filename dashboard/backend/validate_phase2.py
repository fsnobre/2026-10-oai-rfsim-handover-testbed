from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from collectors.kpi_history import KpiHistory, sample_from_state
from collectors.run_artifacts import RunArtifacts
from collectors.telnet_poller import parse_attached_ues, parse_supported_commands
from state_models import live_kpis_from_sources


def validate_run_artifacts_missing() -> None:
    with TemporaryDirectory() as tmp:
        runs, warnings = RunArtifacts(Path(tmp)).list_runs()
        assert runs == []
        assert warnings == []


def validate_run_artifacts_partial() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "results" / "runs" / "20260101_000000_test"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": "20260101_000000_test",
                    "topology": "f1",
                    "status": "pass",
                    "estimated_interruption_ms": 123.4,
                }
            )
        )
        runs, warnings = RunArtifacts(root).list_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "20260101_000000_test"
        assert warnings == []
        detail, detail_warnings = RunArtifacts(root).get_run("20260101_000000_test")
        assert detail is not None
        assert detail["summary"]["status"] == "pass"
        assert any("ping_summary.json" in warning for warning in detail_warnings)


def validate_kpi_history_retention() -> None:
    history = KpiHistory(retention_seconds=1)
    old = datetime.now(timezone.utc) - timedelta(seconds=10)
    history._samples.append({"timestamp": old.isoformat(), "value": "old"})  # noqa: SLF001 - validation helper
    history.add({"value": "new"})
    samples = history.samples()
    assert len(samples) == 1
    assert samples[0]["value"] == "new"


def validate_ue_count_sources() -> None:
    no_current_context = live_kpis_from_sources({"attached_ues": []}, amf_registration_events_seen=3)
    assert no_current_context["ue_count"] is None
    assert no_current_context["ue_count_source"] is None
    assert no_current_context["amf_registration_events_seen"] == 3
    assert no_current_context["amf_registration_events_source"] == "amf_logs_tail"

    with_current_context = live_kpis_from_sources(
        {"attached_ues": [{"rnti": "0x1234"}, {"rnti": "0x5678"}]},
        amf_registration_events_seen=7,
    )
    assert with_current_context["ue_count"] == 2
    assert with_current_context["ue_count_source"] == "telnet"
    assert with_current_context["amf_registration_events_seen"] == 7

    sample = sample_from_state(
        containers=[],
        telnet={"cu": {"ue_count": None, "attached_ues": []}},
        latest_run=None,
        live_kpis=no_current_context,
    )
    assert sample["ue_count"] is None
    assert sample["amf_registration_events_seen"] == 3


def validate_telnet_parsers() -> None:
    assert parse_supported_commands("") == []
    commands = parse_supported_commands("help\nue\nrrc stats\nci trigger_f1_ho\n")
    assert "ue" in commands
    assert "rrc stats" in commands

    ues, warnings = parse_attached_ues("")
    assert ues == []
    assert warnings == []

    ues, warnings = parse_attached_ues("UE id 1 RNTI 0x1234 serving_du DU0")
    assert len(ues) == 1
    assert ues[0]["rnti"] == "0x1234"
    assert warnings == []

    ues, warnings = parse_attached_ues("unexpected telnet output")
    assert ues == []
    assert warnings


def main() -> int:
    validate_run_artifacts_missing()
    validate_run_artifacts_partial()
    validate_kpi_history_retention()
    validate_ue_count_sources()
    validate_telnet_parsers()
    print("Phase 2 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
