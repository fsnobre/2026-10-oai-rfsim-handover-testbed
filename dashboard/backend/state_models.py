from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_freshness(**timestamps: str | None) -> dict[str, str | None]:
    return dict(timestamps)


def empty_live_kpis() -> dict[str, Any]:
    return {
        "ue_count": None,
        "ue_count_source": None,
        "attached_ues": [],
        "amf_registration_events_seen": None,
        "amf_registration_events_source": None,
        "amf_registration_events_window": None,
        "serving_du": None,
        "cqi": None,
        "mcs_dl": None,
        "mcs_ul": None,
        "bler_dl": None,
        "bler_ul": None,
        "bitrate_dl": None,
        "bitrate_ul": None,
        "phr": None,
    }


def live_kpis_from_sources(
    cu_telnet: dict[str, Any],
    amf_registration_events_seen: int | None = None,
) -> dict[str, Any]:
    live_kpis = empty_live_kpis()
    attached_ues = cu_telnet.get("attached_ues", []) or []
    ue_count = len(attached_ues) if attached_ues else cu_telnet.get("ue_count")
    live_kpis.update(
        {
            "ue_count": ue_count,
            "ue_count_source": "telnet" if ue_count is not None else None,
            "attached_ues": attached_ues,
            "amf_registration_events_seen": amf_registration_events_seen,
            "amf_registration_events_source": "amf_logs_tail" if amf_registration_events_seen is not None else None,
            "amf_registration_events_window": "last_500_log_lines" if amf_registration_events_seen is not None else None,
        }
    )
    return live_kpis
