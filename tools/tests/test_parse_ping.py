"""Golden tests for tools/parse_ping.py.

These pin the headline research metric (estimated_interruption_ms) and the
correctness guards documented in guide-measurement-pipeline.md:

* the interruption estimate is (first reply after handover) - (last reply before);
* the precheck ``packets transmitted`` line must NOT be read as the long-capture
  count (the historical parser bug — replies gate summary parsing);
* a contiguous, lossless capture reports 0% loss and valid metrics.

Fixtures are generated deterministically from known timestamps so expected
outputs can be asserted exactly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import parse_ping
import pytest


def reply_line(epoch: float, seq: int, rtt_ms: float, src: str = "192.168.71.135") -> str:
    return f"[{epoch:.6f}] 64 bytes from {src}: icmp_seq={seq} ttl=64 time={rtt_ms} ms"


def iso_z(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def write_events(path: Path, event_epochs: dict[str, float]) -> None:
    lines = ["timestamp,event"]
    for event, epoch in event_epochs.items():
        lines.append(f"{iso_z(epoch)},{event}")
    path.write_text("\n".join(lines) + "\n")


# Base epoch kept small so float subtraction stays exact to the microsecond.
BASE = 100000.0


def test_interruption_is_gap_between_replies(tmp_path: Path):
    raw = tmp_path / "ping_raw.log"
    # Replies at +0, +10, +20 ms (before), then +100, +110 ms (after). The
    # handover fires at +50 ms.
    raw.write_text(
        "\n".join(
            [
                "# ping capture header",
                reply_line(BASE + 0.000, 1, 0.5),
                reply_line(BASE + 0.010, 2, 0.5),
                reply_line(BASE + 0.020, 3, 0.5),
                reply_line(BASE + 0.100, 4, 0.5),
                reply_line(BASE + 0.110, 5, 0.5),
                "5 packets transmitted, 5 received, 0% packet loss",
            ]
        )
        + "\n"
    )
    events_path = tmp_path / "events.csv"
    write_events(events_path, {"handover_trigger_start": BASE + 0.050})

    rows, _ = parse_ping.parse_ping(raw)
    metrics = parse_ping.interruption_metrics(rows, parse_ping.load_events(events_path))

    # last before = +20 ms, first after = +100 ms -> 80 ms gap.
    assert metrics["estimated_interruption_ms"] == pytest.approx(80.0, abs=0.5)
    # first after (+100) - handover (+50) = 50 ms.
    assert metrics["first_ping_after_handover_ms"] == pytest.approx(50.0, abs=0.5)


def test_precheck_stats_line_is_ignored(tmp_path: Path):
    # Regression: a precheck "2 packets transmitted" line appearing BEFORE the
    # long capture must not be read as the capture's transmitted count.
    raw = tmp_path / "ping_raw.log"
    raw.write_text(
        "\n".join(
            [
                "# ping capture header",
                "2 packets transmitted, 2 received, 0% packet loss",  # precheck contamination
                reply_line(BASE + 0.000, 1, 0.4),
                reply_line(BASE + 0.010, 2, 0.4),
                reply_line(BASE + 0.020, 3, 0.4),
                reply_line(BASE + 0.030, 4, 0.4),
                reply_line(BASE + 0.040, 5, 0.4),
                "5 packets transmitted, 5 received, 0% packet loss",  # real long-capture stats
            ]
        )
        + "\n"
    )

    _, stats = parse_ping.parse_ping(raw)

    assert stats["packets_transmitted"] == 5  # not 2
    assert stats["packets_received"] == 5
    assert stats["parsed_reply_count"] == 5
    assert stats["packet_loss_percent"] == 0.0


def test_seamless_contiguous_capture_is_valid_zero_loss(tmp_path: Path):
    raw = tmp_path / "ping_raw.log"
    lines = ["# ping capture header"]
    for seq in range(1, 11):
        lines.append(reply_line(BASE + seq * 0.010, seq, 0.3))
    lines.append("10 packets transmitted, 10 received, 0% packet loss")
    raw.write_text("\n".join(lines) + "\n")

    _, stats = parse_ping.parse_ping(raw)

    assert stats["ping_metrics_valid"] is True
    assert stats["packet_loss_percent"] == 0.0
    assert stats["max_icmp_seq"] == 10


def test_missing_handover_event_yields_null_interruption(tmp_path: Path):
    raw = tmp_path / "ping_raw.log"
    raw.write_text(
        "\n".join([reply_line(BASE + 0.0, 1, 0.5), reply_line(BASE + 0.01, 2, 0.5)]) + "\n"
    )
    rows, _ = parse_ping.parse_ping(raw)

    metrics = parse_ping.interruption_metrics(rows, {})  # no events
    assert metrics["estimated_interruption_ms"] is None
    assert metrics["first_ping_after_handover_ms"] is None


def test_zero_replies_is_invalid(tmp_path: Path):
    raw = tmp_path / "ping_raw.log"
    raw.write_text("# header only, no replies\n1 packets transmitted, 0 received, 100% packet loss\n")

    _, stats = parse_ping.parse_ping(raw)

    assert stats["parsed_reply_count"] == 0
    assert stats["ping_metrics_valid"] is False
    # The pre-reply stats line is ignored, so transmitted falls back to reply count.
    assert stats["packets_transmitted"] in (0, None)
