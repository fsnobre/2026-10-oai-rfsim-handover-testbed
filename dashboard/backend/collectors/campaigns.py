from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRIC_FIELDS = [
    "estimated_interruption_ms",
    "first_ping_after_handover_ms",
    "packet_loss_percent",
    "rtt_avg_ms",
    "iperf_mbps",
]


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"Missing optional artifact: {path.name}"
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return None, f"Could not parse {path.name}: {exc}"
    if not isinstance(data, dict):
        return None, f"Could not parse {path.name}: expected JSON object"
    return data, None


def _read_csv(path: Path) -> tuple[list[dict[str, str]], str | None]:
    if not path.exists():
        return [], f"Missing optional artifact: {path.name}"
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return [], f"Could not parse {path.name}: missing header"
            return list(reader), None
    except Exception as exc:
        return [], f"Could not parse {path.name}: {exc}"


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


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _status_passed(status: Any) -> bool:
    return str(status or "").lower() in {"pass", "passed", "success", "succeeded"}


def _infer_topology(campaign_id: str, rows: list[dict[str, Any]]) -> str | None:
    topologies = [str(row.get("topology")) for row in rows if row.get("topology")]
    if topologies:
        return max(set(topologies), key=topologies.count)
    if "n2_cu_du" in campaign_id:
        return "n2-cu-du"
    if "n2_monolithic" in campaign_id:
        return "n2-monolithic"
    if "f1" in campaign_id:
        return "f1"
    return None


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def statistics_for_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int | None]]:
    stats: dict[str, dict[str, float | int | None]] = {}
    for field in METRIC_FIELDS:
        stats[field] = _stats([value for row in rows if (value := _numeric(row.get(field))) is not None])
    return stats


def _resolve_run_dir(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        return repo_root / value

    if path.exists():
        return path

    parts = path.parts
    try:
        results_index = parts.index("results")
    except ValueError:
        return path

    if len(parts) >= results_index + 3 and parts[results_index + 1] == "runs":
        run_id = parts[results_index + 2]
        return repo_root / "results" / "runs" / run_id

    return path


def _summary_row(run_dir: Path, summary: dict[str, Any] | None, csv_row: dict[str, Any] | None = None) -> dict[str, Any]:
    source = summary or csv_row or {}
    warnings: list[str] = []
    if summary is None:
        warnings.append("summary.json unavailable")
    row = {
        "run_id": source.get("run_id") or run_dir.name,
        "path": str(run_dir),
        "topology": source.get("topology"),
        "status": source.get("status"),
        "handover_triggered": source.get("handover_triggered"),
        "estimated_interruption_ms": _numeric(source.get("estimated_interruption_ms")),
        "first_ping_after_handover_ms": _numeric(source.get("first_ping_after_handover_ms")),
        "packet_loss_percent": _numeric(source.get("packet_loss_percent")),
        "rtt_avg_ms": _numeric(source.get("rtt_avg_ms")),
        "iperf_mbps": _numeric(source.get("iperf_mbps")),
        "start_time": source.get("start_time"),
        "end_time": source.get("end_time"),
        "warnings_count": len(warnings),
        "warnings": warnings,
    }
    if isinstance(row["handover_triggered"], str):
        row["handover_triggered"] = row["handover_triggered"].lower() in {"true", "1", "yes", "on"}
    return row


def _outliers(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    def compact(row: dict[str, Any], metric: str | None = None) -> dict[str, Any]:
        item = {
            "run_id": row.get("run_id"),
            "status": row.get("status"),
            "topology": row.get("topology"),
        }
        if metric:
            item[metric] = row.get(metric)
        return item

    def ranked(metric: str, reverse: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        available = [row for row in rows if _numeric(row.get(metric)) is not None]
        return [compact(row, metric) for row in sorted(available, key=lambda item: float(item[metric]), reverse=reverse)[:limit]]

    return {
        "failed_runs": [compact(row) for row in rows if not _status_passed(row.get("status"))],
        "missing_handover_trigger": [compact(row) for row in rows if row.get("handover_triggered") is not True],
        "missing_ping_metrics": [
            compact(row)
            for row in rows
            if row.get("estimated_interruption_ms") is None
            or row.get("packet_loss_percent") is None
            or row.get("rtt_avg_ms") is None
        ],
        "highest_interruption": ranked("estimated_interruption_ms"),
        "highest_packet_loss": ranked("packet_loss_percent"),
        "highest_rtt_avg": ranked("rtt_avg_ms"),
        "lowest_iperf_mbps": ranked("iperf_mbps", reverse=False),
    }


def _campaign_summary(campaign_id: str, path: Path, rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    run_count = len(rows)
    passed_count = sum(1 for row in rows if _status_passed(row.get("status")))
    failed_count = run_count - passed_count
    starts = [_parse_time(row.get("start_time")) for row in rows]
    ends = [_parse_time(row.get("end_time")) for row in rows]
    stats = statistics_for_rows(rows)
    return {
        "campaign_id": campaign_id,
        "path": str(path),
        "topology": _infer_topology(campaign_id, rows),
        "start_time": _iso(min((item for item in starts if item), default=None)),
        "end_time": _iso(max((item for item in ends if item), default=None)),
        "run_count": run_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate_percent": round((passed_count / run_count) * 100, 3) if run_count else None,
        "handover_triggered_count": sum(1 for row in rows if row.get("handover_triggered") is True),
        "statistics": stats,
        "warning_count": len(warnings) + sum(int(row.get("warnings_count") or 0) for row in rows),
    }


class Campaigns:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.repeated_dir = repo_root / "results" / "repeated"
        self.runs_dir = repo_root / "results" / "runs"

    def list_campaigns(self) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.repeated_dir.exists():
            return [], []
        campaigns: list[dict[str, Any]] = []
        warnings: list[str] = []
        for campaign_dir in sorted((item for item in self.repeated_dir.iterdir() if item.is_dir()), reverse=True):
            detail, detail_warnings = self.get_campaign(campaign_dir.name)
            warnings.extend(f"{campaign_dir.name}: {warning}" for warning in detail_warnings)
            if detail:
                campaigns.append(detail["summary"])
        return campaigns, warnings

    def get_campaign(self, campaign_id: str) -> tuple[dict[str, Any] | None, list[str]]:
        campaign_dir = self.repeated_dir / campaign_id
        if not campaign_dir.exists() or not campaign_dir.is_dir():
            return None, [f"Campaign not found: {campaign_id}"]

        warnings: list[str] = []
        campaign_json, warning = _read_json(campaign_dir / "summary.json")
        if warning and "Missing optional" not in warning:
            warnings.append(warning)
        csv_rows, warning = _read_csv(campaign_dir / "summary.csv")
        if warning and "Missing optional" not in warning:
            warnings.append(warning)

        run_paths = self._run_paths(campaign_dir, campaign_json)
        rows: list[dict[str, Any]] = []
        for index, run_dir in enumerate(run_paths):
            summary, run_warning = _read_json(run_dir / "summary.json")
            if run_warning:
                warnings.append(f"{run_dir.name}: {run_warning}")
            csv_row = csv_rows[index] if index < len(csv_rows) else None
            rows.append(_summary_row(run_dir, summary, csv_row))

        if not rows and csv_rows:
            for row in csv_rows:
                run_id = str(row.get("run_id") or "")
                rows.append(_summary_row(self.runs_dir / run_id, None, row))

        summary = _campaign_summary(campaign_id, campaign_dir, rows, warnings)
        return {
            "campaign_id": campaign_id,
            "path": str(campaign_dir),
            "summary": summary,
            "runs": rows,
            "statistics": summary["statistics"],
            "outliers": _outliers(rows),
            "source_summary": campaign_json,
            "warnings": warnings,
        }, warnings

    def compare(self) -> tuple[dict[str, Any], list[str]]:
        campaigns, warnings = self.list_campaigns()
        by_topology: dict[str, list[dict[str, Any]]] = {}
        for item in campaigns:
            by_topology.setdefault(item.get("topology") or "unknown", []).append(item)

        topology_rows: list[dict[str, Any]] = []
        for topology, summaries in sorted(by_topology.items()):
            synthetic_rows: list[dict[str, Any]] = []
            run_count = 0
            passed_count = 0
            failed_count = 0
            handover_count = 0
            for summary in summaries:
                run_count += int(summary.get("run_count") or 0)
                passed_count += int(summary.get("passed_count") or 0)
                failed_count += int(summary.get("failed_count") or 0)
                handover_count += int(summary.get("handover_triggered_count") or 0)
                detail, detail_warnings = self.get_campaign(str(summary["campaign_id"]))
                warnings.extend(f"{summary['campaign_id']}: {warning}" for warning in detail_warnings)
                if detail:
                    synthetic_rows.extend(detail["runs"])
            topology_rows.append(
                {
                    "topology": topology,
                    "campaign_count": len(summaries),
                    "run_count": run_count,
                    "passed_count": passed_count,
                    "failed_count": failed_count,
                    "pass_rate_percent": round((passed_count / run_count) * 100, 3) if run_count else None,
                    "handover_triggered_count": handover_count,
                    "statistics": statistics_for_rows(synthetic_rows),
                }
            )
        return {"campaigns": campaigns, "topologies": topology_rows}, warnings

    def export_rows(self) -> tuple[list[dict[str, Any]], list[str]]:
        campaigns, warnings = self.list_campaigns()
        rows: list[dict[str, Any]] = []
        for campaign in campaigns:
            detail, detail_warnings = self.get_campaign(str(campaign["campaign_id"]))
            warnings.extend(f"{campaign['campaign_id']}: {warning}" for warning in detail_warnings)
            if not detail:
                continue
            for row in detail["runs"]:
                rows.append({"campaign_id": campaign["campaign_id"], **row})
        return rows, warnings

    def websocket_summary(self) -> dict[str, Any]:
        campaigns, warnings = self.list_campaigns()
        latest = campaigns[0] if campaigns else None
        return {
            "campaign_count": len(campaigns),
            "latest_campaign": latest["campaign_id"] if latest else None,
            "latest_summary": latest,
            "warning_count": len(warnings),
        }

    def _run_paths(self, campaign_dir: Path, campaign_json: dict[str, Any] | None) -> list[Path]:
        paths: list[Path] = []
        runs_file = campaign_dir / "runs.txt"
        if runs_file.exists():
            paths.extend(
                _resolve_run_dir(self.repo_root, line.strip())
                for line in runs_file.read_text().splitlines()
                if line.strip()
            )
        elif campaign_json and isinstance(campaign_json.get("runs"), list):
            paths.extend(_resolve_run_dir(self.repo_root, str(item)) for item in campaign_json["runs"] if item)
        return paths
