"""Detect which testbed topology is actually running.

The dashboard can start and tear down stacks, so the monitored topology cannot be a
startup constant: after deploying N2 the backend would otherwise keep inspecting F1's
containers, probe the wrong telnet endpoint, and post the wrong topology to the handover
action. Detection mirrors ``detect_topology()`` in ``scripts/lib.sh`` so the dashboard and
the CLI always agree on what is running.

Reported honestly: when nothing identifiable is running the result is the fallback with
``detected: None``, never a guess presented as an observation.
"""

from __future__ import annotations

from typing import Any, Container, Iterable

from config import FALLBACK_TOPOLOGY, TOPOLOGIES

# Marker container -> topology, most specific first. Mirrors scripts/lib.sh
# detect_topology(). oai-du0/oai-du1 are deliberately not markers: they exist in both the
# F1 and N2 CU/DU topologies, so only the CU/gNB names disambiguate.
DETECTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("oai-cu", "f1"),
    ("oai-gnb0", "n2-monolithic"),
    ("oai-cu0", "n2-cu-du"),
    ("oai-gnb", "usrp-cots"),
)


def topology_from_container_names(names: Container[str]) -> str | None:
    """The topology implied by the container names present, or None if none matches."""
    for marker, topology in DETECTION_MARKERS:
        if marker in names:
            return topology
    return None


def resolve_topology(
    names: Iterable[str] | None,
    pinned: str | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    """Resolve the topology to monitor and describe how it was resolved.

    ``names`` is the set of container names known to Docker (None when Docker could not
    be reached). ``pinned`` short-circuits detection. The returned ``topology`` is always
    a valid registry key so callers never have to handle an unknown topology.
    """
    if pinned and pinned in TOPOLOGIES:
        return {
            "topology": pinned,
            "mode": "pinned",
            "detected": None,
            "source": "DASHBOARD_TOPOLOGY",
            "warning": None,
            "note": None,
        }

    pin_warning = None
    if pinned:
        pin_warning = f"DASHBOARD_TOPOLOGY={pinned!r} is not a known topology; detecting instead."

    if names is None:
        return {
            "topology": FALLBACK_TOPOLOGY,
            "mode": "auto",
            "detected": None,
            "source": "fallback",
            "warning": warning or pin_warning or "Topology could not be detected; showing the default.",
            "note": None,
        }

    detected = topology_from_container_names(set(names))
    if detected is None:
        # An idle host is a normal state, not a fault, so this is a note rather than a
        # warning: warnings drive the overall status field and would make simply having
        # nothing deployed read as a degraded testbed.
        return {
            "topology": FALLBACK_TOPOLOGY,
            "mode": "auto",
            "detected": None,
            "source": "fallback",
            "warning": pin_warning,
            "note": "No testbed containers are running; showing the default topology until one is deployed.",
        }

    return {
        "topology": detected,
        "mode": "auto",
        "detected": detected,
        "source": "container_probe",
        "warning": pin_warning,
        "note": None,
    }
