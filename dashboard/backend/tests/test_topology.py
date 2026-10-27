"""Topology detection, the DASHBOARD_TOPOLOGY pin, per-topology telnet targets, and
live-latency probe gating."""

from __future__ import annotations

import asyncio

from collectors.live_latency import LiveLatencyMonitor
from collectors.telnet_poller import TelnetPollerRegistry
from collectors.topology_detector import resolve_topology, topology_from_container_names
from config import TOPOLOGIES

# -- detection ----------------------------------------------------------------


def test_marker_containers_match_the_shell_probe_order():
    """Mirrors detect_topology() in scripts/lib.sh so the dashboard and CLI agree."""
    assert topology_from_container_names({"oai-cu", "oai-du0", "oai-du1"}) == "f1"
    assert topology_from_container_names({"oai-gnb0", "oai-gnb1"}) == "n2-monolithic"
    assert topology_from_container_names({"oai-cu0", "oai-cu1", "oai-du0"}) == "n2-cu-du"
    assert topology_from_container_names({"oai-gnb"}) == "usrp-cots"
    assert topology_from_container_names({"mysql", "oai-amf"}) is None


def test_f1_wins_over_n2_cu_du_when_both_markers_are_present():
    """oai-du0/oai-du1 exist in both topologies, so only the CU names disambiguate; a
    leftover oai-cu must not be read as n2-cu-du."""
    assert topology_from_container_names({"oai-cu", "oai-cu0"}) == "f1"


def test_detection_drives_the_resolved_topology():
    result = resolve_topology({"oai-gnb0", "oai-gnb1", "oai-nr-ue"})
    assert result["topology"] == "n2-monolithic"
    assert result["detected"] == "n2-monolithic"
    assert result["mode"] == "auto"
    assert result["source"] == "container_probe"


def test_pin_short_circuits_detection():
    result = resolve_topology({"oai-gnb0"}, pinned="f1")
    assert result["topology"] == "f1"
    assert result["mode"] == "pinned"
    assert result["detected"] is None


def test_unknown_pin_falls_back_to_detection_with_a_warning():
    result = resolve_topology({"oai-gnb0"}, pinned="not-a-topology")
    assert result["topology"] == "n2-monolithic"
    assert result["mode"] == "auto"
    assert "not a known topology" in result["warning"]


def test_nothing_running_reports_the_default_without_claiming_detection():
    result = resolve_topology(set())
    assert result["topology"] == "f1"
    assert result["detected"] is None
    assert result["source"] == "fallback"
    # An idle host is a note, not a warning: warnings drive the overall status field, so
    # having nothing deployed must not read as a degraded testbed.
    assert result["warning"] is None
    assert "No testbed containers are running" in result["note"]


def test_every_resolution_carries_the_same_keys():
    """Consumers read warning/note unconditionally, so no branch may omit them."""
    results = [
        resolve_topology({"oai-cu"}),
        resolve_topology(set()),
        resolve_topology(None, warning="docker down"),
        resolve_topology({"oai-cu"}, pinned="f1"),
        resolve_topology({"oai-cu"}, pinned="nonsense"),
    ]
    for result in results:
        assert set(result) == {"topology", "mode", "detected", "source", "warning", "note"}


def test_docker_unavailable_is_distinguished_from_nothing_running():
    result = resolve_topology(None, warning="Docker API unavailable for topology detection: boom")
    assert result["topology"] == "f1"
    assert result["detected"] is None
    assert "Docker API unavailable" in result["warning"]


def test_every_detected_topology_is_a_registry_key():
    for _marker, topology in [("oai-cu", "f1"), ("oai-gnb0", "n2-monolithic"), ("oai-cu0", "n2-cu-du"), ("oai-gnb", "usrp-cots")]:
        assert topology in TOPOLOGIES


# -- telnet targets -----------------------------------------------------------


def test_primary_telnet_node_per_topology():
    """The control node used for handover: CU for F1, source gNB/CU for N2. This was
    previously hardwired to the F1 CU regardless of topology."""
    assert TOPOLOGIES["f1"].primary_telnet_node().telnet_host == "192.168.70.150"
    assert TOPOLOGIES["n2-monolithic"].primary_telnet_node().telnet_host == "192.168.70.160"
    assert TOPOLOGIES["n2-cu-du"].primary_telnet_node().telnet_host == "192.168.70.150"
    assert TOPOLOGIES["usrp-cots"].primary_telnet_node() is None


def test_registry_returns_a_distinct_poller_per_endpoint():
    registry = TelnetPollerRegistry()
    f1 = registry.for_topology(TOPOLOGIES["f1"])
    n2 = registry.for_topology(TOPOLOGIES["n2-monolithic"])
    assert (f1.host, f1.port) == ("192.168.70.150", 9090)
    assert (n2.host, n2.port) == ("192.168.70.160", 9090)
    assert f1 is not n2
    # Same endpoint reuses the poller, keeping its capability cache.
    assert registry.for_topology(TOPOLOGIES["f1"]) is f1


def test_topology_without_a_telnet_endpoint_is_reported_honestly():
    registry = TelnetPollerRegistry()
    assert registry.for_topology(TOPOLOGIES["usrp-cots"]) is None
    state = TelnetPollerRegistry.no_endpoint_state()["cu"]
    assert state["reachable"] is False
    assert state["host"] is None
    assert state["ue_count"] is None


# -- live latency gating ------------------------------------------------------


def test_probe_is_skipped_when_the_ue_container_is_not_running():
    monitor = LiveLatencyMonitor()
    containers = [{"name": "oai-nr-ue", "status": "exited"}]
    result = asyncio.run(monitor.sample(containers=containers, topology=TOPOLOGIES["f1"]))
    assert result is None
    state = monitor.state()
    assert state["probing"] is False
    assert "not running" in state["skip_reason"]
    assert state["samples"] == []


def test_probe_is_skipped_for_a_topology_with_no_ue_container():
    monitor = LiveLatencyMonitor()
    result = asyncio.run(monitor.sample(containers=[], topology=TOPOLOGIES["usrp-cots"]))
    assert result is None
    assert "no UE container" in monitor.state()["skip_reason"]


def test_probe_target_follows_the_topology_ue_container():
    monitor = LiveLatencyMonitor()
    asyncio.run(monitor.sample(containers=[], topology=TOPOLOGIES["n2-monolithic"]))
    assert monitor.state()["container"] == "oai-nr-ue"


def test_stale_samples_are_dropped_when_probing_stops():
    """A chart that keeps showing old RTTs after the UE goes away would read as live."""
    monitor = LiveLatencyMonitor()
    monitor._samples.append({"reachable": True, "rtt_ms": 8.0})
    asyncio.run(monitor.sample(containers=[{"name": "oai-nr-ue", "status": "exited"}], topology=TOPOLOGIES["f1"]))
    assert monitor.state()["samples"] == []
