#!/usr/bin/env python3
"""Parse Linux ping -D output into CSV and summary metrics."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

RE_REPLY = re.compile(
    r"^\[(?P<ts>\d+(?:\.\d+)?)\]\s+"
    r"(?P<bytes>\d+)\s+bytes\s+from\s+(?P<from>\S+):\s+"
    r"icmp_seq=(?P<seq>\d+).*?\btime=(?P<rtt>\d+(?:\.\d+)?)\s*ms"
)
RE_STATS = re.compile(
    r"(?P<tx>\d+)\s+packets transmitted,\s+"
    r"(?P<rx>\d+)\s+(?:packets )?received,.*?"
    r"(?P<loss>\d+(?:\.\d+)?)%\s+packet loss"
)
RE_RTT = re.compile(
    r"(?:rtt|round-trip).*?=\s+"
    r"(?P<min>\d+(?:\.\d+)?)/(?P<avg>\d+(?:\.\d+)?)/"
    r"(?P<max>\d+(?:\.\d+)?)/(?P<mdev>\d+(?:\.\d+)?)\s+ms"
)


def parse_iso_utc(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def load_events(path: Path | None) -> dict[str, float]:
    if not path or not path.exists():
        return {}

    events: dict[str, float] = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event = row.get("event", "")
            timestamp = row.get("timestamp", "")
            if not event or not timestamp:
                continue
            try:
                events.setdefault(event, parse_iso_utc(timestamp))
            except ValueError:
                continue
    return events


def parse_ping(raw_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    stats: dict[str, object] = {
        "packets_transmitted": None,
        "packets_received": None,
        "packet_loss_percent": None,
        "rtt_min_ms": None,
        "rtt_avg_ms": None,
        "rtt_max_ms": None,
        "parsed_reply_count": 0,
        "max_icmp_seq": None,
    }
    final_capture_stats: dict[str, float | int] | None = None
    final_capture_rtt: dict[str, float] | None = None
    long_capture_started = False

    with raw_path.open(errors="replace") as handle:
        for line in handle:
            reply = RE_REPLY.search(line)
            if reply:
                long_capture_started = True
                ts = float(reply.group("ts"))
                rows.append(
                    {
                        "timestamp_unix": f"{ts:.6f}",
                        "timestamp_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z"),
                        "icmp_seq": int(reply.group("seq")),
                        "bytes": int(reply.group("bytes")),
                        "from": reply.group("from"),
                        "rtt_ms": float(reply.group("rtt")),
                    }
                )
                continue

            summary = RE_STATS.search(line)
            if summary and long_capture_started:
                final_capture_stats = {
                    "packets_transmitted": int(summary.group("tx")),
                    "packet_loss_percent": float(summary.group("loss")),
                }
                continue

            rtt = RE_RTT.search(line)
            if rtt and long_capture_started:
                final_capture_rtt = {
                    "rtt_min_ms": float(rtt.group("min")),
                    "rtt_avg_ms": float(rtt.group("avg")),
                    "rtt_max_ms": float(rtt.group("max")),
                }

    parsed_reply_count = len(rows)
    max_icmp_seq = max((int(row["icmp_seq"]) for row in rows), default=None)

    stats["parsed_reply_count"] = parsed_reply_count
    stats["max_icmp_seq"] = max_icmp_seq
    stats["packets_received"] = parsed_reply_count

    if final_capture_stats is not None:
        stats["packets_transmitted"] = final_capture_stats["packets_transmitted"]
    else:
        stats["packets_transmitted"] = max_icmp_seq or parsed_reply_count

    tx = int(stats["packets_transmitted"] or 0)
    rx = int(stats["packets_received"] or 0)
    stats["packet_loss_percent"] = round(((tx - rx) / tx) * 100, 3) if tx else None

    if final_capture_rtt is not None:
        stats.update(final_capture_rtt)
    elif rows:
        rtts = [float(row["rtt_ms"]) for row in rows]
        stats["rtt_min_ms"] = min(rtts)
        stats["rtt_avg_ms"] = sum(rtts) / len(rtts)
        stats["rtt_max_ms"] = max(rtts)

    stats["ping_metrics_valid"] = parsed_reply_count > 0
    stats["ping_error"] = None if stats["ping_metrics_valid"] else "ping parser found zero usable samples"

    return rows, stats


def interruption_metrics(rows: list[dict[str, object]], events: dict[str, float]) -> dict[str, float | None]:
    handover_ts = events.get("handover_trigger_start") or events.get("before_handover")
    if not handover_ts:
        return {
            "estimated_interruption_ms": None,
            "first_ping_after_handover_ms": None,
        }

    reply_times = [float(row["timestamp_unix"]) for row in rows]
    before = [ts for ts in reply_times if ts < handover_ts]
    after = [ts for ts in reply_times if ts >= handover_ts]

    if not after:
        return {
            "estimated_interruption_ms": None,
            "first_ping_after_handover_ms": None,
        }

    first_after_ms = max(0.0, (after[0] - handover_ts) * 1000)

    if before:
        estimated = max(0.0, (after[0] - before[-1]) * 1000)
    else:
        estimated = first_after_ms

    return {
        "estimated_interruption_ms": round(estimated, 3),
        "first_ping_after_handover_ms": round(first_after_ms, 3),
    }


def write_csv(rows: list[dict[str, object]], csv_path: Path) -> None:
    fieldnames = ["timestamp_unix", "timestamp_utc", "icmp_seq", "bytes", "from", "rtt_ms"]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args()

    rows, stats = parse_ping(args.raw)
    events = load_events(args.events)
    metrics = {**stats, **interruption_metrics(rows, events)}

    write_csv(rows, args.csv)

    if args.summary_out:
        args.summary_out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(metrics, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
