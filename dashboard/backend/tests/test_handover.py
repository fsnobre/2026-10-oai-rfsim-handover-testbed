"""Handover/mobility observability and message-flow reconstruction
(formerly validate_phase3), plus telnet-observation honesty."""

from pathlib import Path

import validate_phase3
from collectors.handover_events import HandoverEvents, telnet_observation
from collectors.telnet_poller import TelnetPoller, TelnetPollerRegistry
from config import TOPOLOGIES


def test_missing_runs():
    validate_phase3.validate_missing_runs()


def test_partial_summary_only():
    validate_phase3.validate_partial_summary_only()


def test_events_and_message_flow():
    validate_phase3.validate_events_and_message_flow()


def test_sparse_message_flow_unknowns():
    validate_phase3.validate_sparse_message_flow_unknowns()


def test_live_status_does_not_fabricate_du():
    validate_phase3.validate_live_status_does_not_fabricate_du()


def test_duration_table():
    validate_phase3.validate_duration_table()


def test_bounded_artifact_log_tail():
    validate_phase3.validate_bounded_artifact_log_tail()


def test_malformed_artifacts_warn():
    validate_phase3.validate_malformed_artifacts_warn()


# -- telnet observation -------------------------------------------------------
# "Never probed" and "probed and failed" are different claims. Passive polling is off by
# default, so conflating them reported a failure that was never observed and marked a
# healthy stack degraded.


def test_observation_classes():
    assert telnet_observation({"reachable": True}) == "reachable"
    assert telnet_observation({"reachable": False, "polling_enabled": True}) == "unreachable"
    # An unannotated telnet dict is treated as a real probe result.
    assert telnet_observation({"reachable": False}) == "unreachable"


def test_disabled_polling_is_not_an_unreachable_claim():
    """The default configuration: the poller exists but was never asked to run."""
    state = TelnetPoller().disabled_state()["cu"]
    assert telnet_observation(state) == "polling_disabled"


def test_topology_without_a_telnet_node_is_its_own_class():
    state = TelnetPollerRegistry.no_endpoint_state()["cu"]
    assert telnet_observation(state) == "no_endpoint"


def _live_status(cu: dict) -> dict:
    return HandoverEvents(Path("/tmp/nonexistent")).live_status(
        TOPOLOGIES["f1"],
        containers=[],
        telnet={"cu": cu},
        recent_events=[],
    )


def test_unprobed_telnet_reads_as_not_observed_without_warning():
    status = _live_status(TelnetPoller().disabled_state()["cu"])
    assert status["readiness"] == "not_observed"
    assert status["cu_telnet_status"] == "polling_disabled"
    assert status["cu_telnet_reachable"] is False
    # No warning: a deliberately disabled probe is not a fault, and warnings mark the
    # whole dashboard degraded.
    assert status["warnings"] == []


def test_probed_and_unreachable_still_warns():
    status = _live_status({"reachable": False, "polling_enabled": True})
    assert status["readiness"] == "degraded"
    assert status["cu_telnet_status"] == "unreachable"
    assert any("probed and is not reachable" in warning for warning in status["warnings"])


def test_reachable_telnet_is_ready():
    status = _live_status({"reachable": True, "polling_enabled": True})
    assert status["readiness"] == "ready"
    assert status["cu_telnet_status"] == "reachable"
    assert status["warnings"] == []


def test_missing_required_containers_still_dominate():
    """A stack that is actually down outranks any telnet nuance."""
    status = HandoverEvents(Path("/tmp/nonexistent")).live_status(
        TOPOLOGIES["f1"],
        containers=[{"name": "oai-cu0", "required": True, "status": "exited"}],
        telnet={"cu": TelnetPoller().disabled_state()["cu"]},
        recent_events=[],
    )
    assert status["readiness"] == "unavailable"
