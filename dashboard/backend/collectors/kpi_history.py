from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any


class KpiHistory:
    def __init__(self, retention_seconds: int = 600) -> None:
        self.retention_seconds = retention_seconds
        self._samples: deque[dict[str, Any]] = deque()

    def add(self, sample: dict[str, Any]) -> dict[str, Any]:
        enriched = {"timestamp": datetime.now(timezone.utc).isoformat(), **sample}
        self._samples.append(enriched)
        self._prune()
        return enriched

    def samples(self) -> list[dict[str, Any]]:
        self._prune()
        return list(self._samples)

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - self.retention_seconds
        while self._samples:
            try:
                sample_ts = datetime.fromisoformat(str(self._samples[0]["timestamp"])).timestamp()
            except (KeyError, ValueError):
                self._samples.popleft()
                continue
            if sample_ts >= cutoff:
                break
            self._samples.popleft()


def sample_from_state(
    containers: list[dict[str, Any]],
    telnet: dict[str, Any],
    latest_run: dict[str, Any] | None,
    live_kpis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cu = telnet.get("cu", {})
    live = live_kpis or {}
    return {
        "containers": {
            item["name"]: {
                "status": item.get("status"),
                "health": item.get("health"),
                "indicator": item.get("indicator"),
            }
            for item in containers
        },
        "cu_telnet_reachable": cu.get("reachable"),
        "ue_count": live.get("ue_count", cu.get("ue_count")),
        "ue_count_source": live.get("ue_count_source"),
        "attached_ues": live.get("attached_ues", cu.get("attached_ues", [])),
        "amf_registration_events_seen": live.get("amf_registration_events_seen"),
        "amf_registration_events_source": live.get("amf_registration_events_source"),
        "amf_registration_events_window": live.get("amf_registration_events_window"),
        "latest_run": {
            "estimated_interruption_ms": (latest_run or {}).get("estimated_interruption_ms"),
            "packet_loss_percent": (latest_run or {}).get("packet_loss_percent"),
            "rtt_avg_ms": (latest_run or {}).get("rtt_avg_ms"),
            "rtt_min_ms": (latest_run or {}).get("rtt_min_ms"),
            "rtt_max_ms": (latest_run or {}).get("rtt_max_ms"),
            "iperf_mbps": (latest_run or {}).get("iperf_mbps"),
            "iperf_jitter_ms": (latest_run or {}).get("iperf_jitter_ms"),
            "iperf_lost_percent": (latest_run or {}).get("iperf_lost_percent"),
        },
    }
