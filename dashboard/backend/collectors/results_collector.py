from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from collectors.run_artifacts import RunArtifacts


class ResultsCollector:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._artifacts = RunArtifacts(repo_root)

    def latest(self) -> tuple[dict[str, Any] | None, list[str]]:
        runs, warnings = self._artifacts.list_runs()
        runs_with_summary = [run for run in runs if run.get("has_summary")]
        if not runs_with_summary:
            return None, warnings

        latest = runs_with_summary[0]
        run_dir = Path(str(latest["path"]))
        try:
            summary = json.loads((run_dir / "summary.json").read_text())
        except Exception as exc:
            return None, [*warnings, f"Could not read latest run summary {run_dir / 'summary.json'}: {exc}"]

        iperf_summary = None
        iperf_path = run_dir / "iperf_summary.json"
        if iperf_path.exists():
            try:
                iperf_summary = json.loads(iperf_path.read_text())
            except Exception as exc:
                warnings.append(f"Could not read iperf summary {iperf_path}: {exc}")

        return {
            "run_id": summary.get("run_id", run_dir.name),
            "path": str(run_dir),
            "topology": summary.get("topology"),
            "status": summary.get("status"),
            "start_time": summary.get("start_time"),
            "end_time": summary.get("end_time"),
            "handover_triggered": summary.get("handover_triggered"),
            "estimated_interruption_ms": summary.get("estimated_interruption_ms"),
            "first_ping_after_handover_ms": summary.get("first_ping_after_handover_ms"),
            "packet_loss_percent": summary.get("packet_loss_percent"),
            "rtt_avg_ms": summary.get("rtt_avg_ms"),
            "rtt_min_ms": summary.get("rtt_min_ms"),
            "rtt_max_ms": summary.get("rtt_max_ms"),
            "iperf_status": summary.get("iperf_status"),
            "iperf_mbps": summary.get("iperf_mbps"),
            "iperf_jitter_ms": summary.get("iperf_jitter_ms"),
            "iperf_lost_percent": summary.get("iperf_lost_percent"),
            "iperf_summary": iperf_summary,
        }, warnings
