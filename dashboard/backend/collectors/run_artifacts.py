from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

SUMMARY_FIELDS = [
    "run_id",
    "topology",
    "status",
    "start_time",
    "end_time",
    "handover_triggered",
    "estimated_interruption_ms",
    "packet_loss_percent",
    "rtt_min_ms",
    "rtt_avg_ms",
    "rtt_max_ms",
    "iperf_status",
    "iperf_protocol",
    "iperf_mbps",
    "iperf_jitter_ms",
    "iperf_lost_percent",
]


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"Missing optional artifact: {path.name}"
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:
        return None, f"Could not parse {path.name}: {exc}"


def _run_id_from_dir(path: Path) -> str:
    return path.name


def _summary_projection(run_dir: Path, summary: dict[str, Any] | None) -> dict[str, Any]:
    source = summary or {}
    return {field: source.get(field) for field in SUMMARY_FIELDS} | {
        "run_id": source.get("run_id") or _run_id_from_dir(run_dir),
        "path": str(run_dir),
        "has_summary": summary is not None,
    }


def _read_events(path: Path) -> tuple[list[dict[str, str]], str | None]:
    if not path.exists():
        return [], "Missing optional artifact: events.csv"
    try:
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle)), None
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
        try:
            rtt_ms = float(row["rtt_ms"]) if row.get("rtt_ms") not in {None, ""} else None
        except ValueError:
            rtt_ms = None
        samples.append(
            {
                "timestamp_unix": row.get("timestamp_unix"),
                "timestamp_utc": row.get("timestamp_utc"),
                "icmp_seq": int(row["icmp_seq"]) if str(row.get("icmp_seq", "")).isdigit() else None,
                "rtt_ms": rtt_ms,
            }
        )
    return samples, None


class RunArtifacts:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.runs_dir = repo_root / "results" / "runs"

    def list_runs(self) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.runs_dir.exists():
            return [], []

        runs: list[dict[str, Any]] = []
        warnings: list[str] = []
        for run_dir in sorted((p for p in self.runs_dir.iterdir() if p.is_dir()), reverse=True):
            summary, warning = _read_json(run_dir / "summary.json")
            if warning and "Missing optional" not in warning:
                warnings.append(f"{run_dir.name}: {warning}")
            runs.append(_summary_projection(run_dir, summary))
        return runs, warnings

    def get_run(self, run_id: str) -> tuple[dict[str, Any] | None, list[str]]:
        run_dir = self.runs_dir / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            return None, [f"Run not found: {run_id}"]

        warnings: list[str] = []
        summary, warning = _read_json(run_dir / "summary.json")
        if warning:
            warnings.append(warning)
        ping_summary, warning = _read_json(run_dir / "ping_summary.json")
        if warning:
            warnings.append(warning)
        iperf_summary, warning = _read_json(run_dir / "iperf_summary.json")
        if warning:
            warnings.append(warning)
        events, warning = _read_events(run_dir / "events.csv")
        if warning:
            warnings.append(warning)
        ping_samples, warning = _read_ping_samples(run_dir / "ping.csv")
        if warning:
            warnings.append(warning)

        return {
            "run_id": run_id,
            "path": str(run_dir),
            "summary": summary,
            "ping_summary": ping_summary,
            "iperf_summary": iperf_summary,
            "events": events,
            "ping_samples": ping_samples,
            "warnings": warnings,
        }, warnings
