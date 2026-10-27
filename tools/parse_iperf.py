#!/usr/bin/env python3
"""Parse iperf3 JSON output into a compact summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def bps_to_mbps(value: float | int | None) -> float | None:
    if value is None:
        return None
    return float(value) / 1_000_000.0


def parse_summary(raw_path: Path) -> dict[str, object]:
    with raw_path.open() as handle:
        data = json.load(handle)

    start = data.get("start", {})
    end = data.get("end", {})
    test_start = start.get("test_start", {})
    protocol = str(test_start.get("protocol", "")).upper() or None

    summary: dict[str, object] = {
        "protocol": protocol,
        "duration_seconds": test_start.get("duration"),
        "server_host": start.get("connected", [{}])[0].get("remote_host") if start.get("connected") else None,
        "local_host": start.get("connected", [{}])[0].get("local_host") if start.get("connected") else None,
        "raw_json_valid": True,
    }

    if protocol == "UDP":
        udp = end.get("sum", {})
        summary.update(
            {
                "bits_per_second": udp.get("bits_per_second"),
                "mbps": bps_to_mbps(udp.get("bits_per_second")),
                "jitter_ms": udp.get("jitter_ms"),
                "lost_packets": udp.get("lost_packets"),
                "packets": udp.get("packets"),
                "lost_percent": udp.get("lost_percent"),
            }
        )
    else:
        receiver = end.get("sum_received") or end.get("sum") or {}
        sender = end.get("sum_sent") or {}
        summary.update(
            {
                "bits_per_second": receiver.get("bits_per_second"),
                "mbps": bps_to_mbps(receiver.get("bits_per_second")),
                "sender_bits_per_second": sender.get("bits_per_second"),
                "sender_mbps": bps_to_mbps(sender.get("bits_per_second")),
                "retransmits": sender.get("retransmits"),
            }
        )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    args = parser.parse_args()

    summary = parse_summary(args.raw)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
