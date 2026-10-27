from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NodeConfig:
    role: str
    container: str
    service: str | None = None
    ip: str | None = None
    required: bool = True
    telnet_host: str | None = None
    telnet_port: int | None = None


@dataclass(frozen=True)
class TopologyConfig:
    name: str
    radio_mode: str
    handover_type: str
    ran_compose: str
    compose_files: tuple[str, ...]
    experiment_config: str
    nodes: tuple[NodeConfig, ...]
    handover_command: str | None = None

    def primary_telnet_node(self) -> NodeConfig | None:
        """The node whose telnet endpoint carries handover control for this topology:
        the CU for F1, the source gNB/CU for N2. Nodes are declared source-first, so the
        first node carrying a telnet endpoint is the right one. None for usrp-cots."""
        return next((node for node in self.nodes if node.telnet_host), None)

    def ue_node(self) -> NodeConfig | None:
        """The in-container UE, when the topology has one. usrp-cots has no UE container
        (the UE is an external COTS handset), so this is None there."""
        return next((node for node in self.nodes if node.role == "ue"), None)


_repo_root_env = os.environ.get("DASHBOARD_REPO_ROOT")
REPO_ROOT = Path(_repo_root_env) if _repo_root_env else Path(__file__).resolve().parents[2]
POLL_INTERVAL_SECONDS = float(os.environ.get("DASHBOARD_POLL_INTERVAL_SECONDS", "1"))

# The topology the dashboard monitors is normally detected from the running containers
# (collectors/topology_detector.py), so the dashboard follows a deploy/teardown without a
# restart. DASHBOARD_TOPOLOGY pins it instead, as an escape hatch; unset or "auto" means
# detect. Falls back to F1 when nothing is running and nothing is pinned.
FALLBACK_TOPOLOGY = "f1"
_topology_env = os.environ.get("DASHBOARD_TOPOLOGY", "").strip().lower()
TOPOLOGY_PIN: str | None = _topology_env if _topology_env and _topology_env != "auto" else None


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"true", "1", "yes", "on"}


def _bounded_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(1, min(value, maximum))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


# Refresh tiers for the background state collector (collectors/snapshot.py). The fast
# tier drives the WebSocket publish rate; the medium and slow tiers cache expensive
# sources (bounded Docker log reads, run/campaign artifact scans) between publishes.
MEDIUM_INTERVAL_SECONDS = _bounded_float("DASHBOARD_MEDIUM_INTERVAL_SECONDS", 5.0, 1.0, 600.0)
SLOW_INTERVAL_SECONDS = _bounded_float("DASHBOARD_SLOW_INTERVAL_SECONDS", 30.0, 1.0, 3600.0)


DASHBOARD_ENABLE_ACTIONS = _env_true("DASHBOARD_ENABLE_ACTIONS")
DASHBOARD_ENABLE_TELNET_POLLING = _env_true("DASHBOARD_ENABLE_TELNET_POLLING")

# Optional static bearer token guarding /api/actions/* and /ws. Empty = disabled
# (lab default). See dashboard/README.md "Authentication".
DASHBOARD_API_TOKEN = os.environ.get("DASHBOARD_API_TOKEN", "").strip()


def _cors_origins() -> list[str]:
    raw = os.environ.get("DASHBOARD_CORS_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


DASHBOARD_CORS_ORIGINS = _cors_origins()
ACTION_TRIGGER_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_TRIGGER_TIMEOUT_SECONDS", 180, 3600)
ACTION_MEASURE_INTERRUPTION_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_MEASURE_INTERRUPTION_TIMEOUT_SECONDS", 180, 3600)
ACTION_SMOKE_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_SMOKE_TIMEOUT_SECONDS", 900, 3600)
ACTION_REPEATED_SMOKE_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_REPEATED_SMOKE_TIMEOUT_SECONDS", 3600, 14400)
# up.sh brings up core + RAN and waits for the UE data plane; down.sh is quick.
ACTION_DEPLOY_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_DEPLOY_TIMEOUT_SECONDS", 600, 3600)
ACTION_TEARDOWN_TIMEOUT_SECONDS = _bounded_int("DASHBOARD_TEARDOWN_TIMEOUT_SECONDS", 300, 3600)

CORE_NODES: tuple[NodeConfig, ...] = (
    NodeConfig("core", "mysql", "mysql", "192.168.70.131", required=False),
    NodeConfig("core", "oai-nrf", "nrf", "192.168.70.130", required=False),
    NodeConfig("core", "oai-udr", "udr", "192.168.70.136", required=False),
    NodeConfig("core", "oai-udm", "udm", "192.168.70.137", required=False),
    NodeConfig("core", "oai-ausf", "ausf", "192.168.70.138", required=False),
    NodeConfig("core", "oai-amf", "amf", "192.168.70.132"),
    NodeConfig("core", "oai-smf", "smf", "192.168.70.133"),
    NodeConfig("core", "oai-upf", "upf", "192.168.70.134"),
    NodeConfig("external", "oai-ext-dn", "ext-dn", "192.168.70.135"),
)

TOPOLOGIES: dict[str, TopologyConfig] = {
    "f1": TopologyConfig(
        name="f1",
        radio_mode="rfsim",
        handover_type="f1",
        ran_compose="gnb-docker-compose.yaml",
        compose_files=("oai-cn5g/docker-compose.yaml", "gnb-docker-compose.yaml"),
        experiment_config="experiments/manual_f1_handover/config.yaml",
        handover_command="ci trigger_f1_ho",
        nodes=CORE_NODES
        + (
            NodeConfig("cu", "oai-cu", "cu", "192.168.70.150", telnet_host="192.168.70.150", telnet_port=9090),
            NodeConfig("du", "oai-du0", "du0", "192.168.70.171"),
            NodeConfig("du", "oai-du1", "du1", "192.168.70.172"),
            NodeConfig("ue", "oai-nr-ue", "nr-ue", "192.168.70.181"),
        ),
    ),
    "n2-monolithic": TopologyConfig(
        name="n2-monolithic",
        radio_mode="rfsim",
        handover_type="n2",
        ran_compose="experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml",
        compose_files=(
            "oai-cn5g/docker-compose.yaml",
            "experiments/n2_handover/topology_a_monolithic/gnb-docker-compose.yaml",
        ),
        experiment_config="experiments/n2_handover/config.yaml",
        nodes=CORE_NODES
        + (
            NodeConfig("gnb", "oai-gnb0", "gnb0", "192.168.70.160", telnet_host="192.168.70.160", telnet_port=9090),
            NodeConfig("gnb", "oai-gnb1", "gnb1", "192.168.70.161", telnet_host="192.168.70.161", telnet_port=9090),
            NodeConfig("ue", "oai-nr-ue", "nr-ue", "192.168.70.181"),
        ),
    ),
    "n2-cu-du": TopologyConfig(
        name="n2-cu-du",
        radio_mode="rfsim",
        handover_type="n2",
        ran_compose="experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml",
        compose_files=(
            "oai-cn5g/docker-compose.yaml",
            "experiments/n2_handover/topology_b_cu_du/gnb-docker-compose.yaml",
        ),
        experiment_config="experiments/n2_handover/config.yaml",
        nodes=CORE_NODES
        + (
            NodeConfig("cu", "oai-cu0", "cu0", "192.168.70.150", telnet_host="192.168.70.150", telnet_port=9090),
            NodeConfig("du", "oai-du0", "du0", "192.168.70.171"),
            NodeConfig("cu", "oai-cu1", "cu1", "192.168.70.155", telnet_host="192.168.70.155", telnet_port=9090),
            NodeConfig("du", "oai-du1", "du1", "192.168.70.172"),
            NodeConfig("ue", "oai-nr-ue", "nr-ue", "192.168.70.181"),
        ),
    ),
    "usrp-cots": TopologyConfig(
        name="usrp-cots",
        radio_mode="usrp",
        handover_type="none",
        ran_compose="experiments/usrp_x310/gnb-docker-compose.yaml",
        compose_files=("oai-cn5g/docker-compose.yaml", "experiments/usrp_x310/gnb-docker-compose.yaml"),
        experiment_config="experiments/usrp_x310/config.yaml",
        nodes=CORE_NODES
        + (
            NodeConfig("gnb", "oai-gnb", "gnb", None),
        ),
    ),
}


def topology_by_name(name: str | None) -> TopologyConfig:
    return TOPOLOGIES.get(name or "", TOPOLOGIES[FALLBACK_TOPOLOGY])


def active_topology() -> TopologyConfig:
    """The statically configured topology, ignoring detection. Live state uses the
    detected topology carried on the snapshot; this is the startup/fallback value."""
    return topology_by_name(TOPOLOGY_PIN)


def repo_path(relative: str) -> Path:
    return REPO_ROOT / relative
