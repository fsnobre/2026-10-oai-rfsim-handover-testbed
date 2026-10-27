from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import docker
from config import TopologyConfig
from docker.errors import DockerException, NotFound


def _indicator(status: str, health: str | None) -> str:
    if status == "running" and health == "healthy":
        return "green"
    if status == "running" and health in {None, "none"}:
        return "orange"
    if status in {"created", "restarting", "paused"}:
        return "orange"
    return "red"


def _health(attrs: dict[str, Any]) -> str | None:
    health = attrs.get("State", {}).get("Health")
    if not health:
        return None
    return health.get("Status")


def _uptime_seconds(attrs: dict[str, Any]) -> float | None:
    started_at = attrs.get("State", {}).get("StartedAt")
    if not started_at or started_at.startswith("0001-"):
        return None
    try:
        parsed = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def _ips(attrs: dict[str, Any]) -> dict[str, str]:
    networks = attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
    result: dict[str, str] = {}
    for name, data in networks.items():
        ip = data.get("IPAddress")
        if ip:
            result[name] = ip
    return result


class DockerMonitor:
    def __init__(self) -> None:
        self._client = None
        self._warning: str | None = None

    def _docker(self):
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def collect(self, topology: TopologyConfig) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        containers: list[dict[str, Any]] = []

        try:
            client = self._docker()
            client.ping()
            self._warning = None
        except DockerException as exc:
            self._client = None
            self._warning = f"Docker API unavailable: {exc}"
            warnings.append(self._warning)
            return [
                {
                    "name": node.container,
                    "service": node.service,
                    "role": node.role,
                    "expected_ip": node.ip,
                    "exists": False,
                    "status": "docker_unavailable",
                    "health": None,
                    "indicator": "red",
                    "required": node.required,
                }
                for node in topology.nodes
            ], warnings

        for node in topology.nodes:
            base = {
                "name": node.container,
                "service": node.service,
                "role": node.role,
                "expected_ip": node.ip,
                "required": node.required,
                "telnet_host": node.telnet_host,
                "telnet_port": node.telnet_port,
            }
            try:
                container = client.containers.get(node.container)
                attrs = container.attrs
                health = _health(attrs)
                status = container.status or attrs.get("State", {}).get("Status", "unknown")
                containers.append(
                    base
                    | {
                        "exists": True,
                        "status": status,
                        "health": health,
                        "indicator": _indicator(status, health),
                        "image": attrs.get("Config", {}).get("Image"),
                        "uptime_seconds": _uptime_seconds(attrs),
                        "ips": _ips(attrs),
                    }
                )
            except NotFound:
                containers.append(base | {"exists": False, "status": "missing", "health": None, "indicator": "red"})
            except DockerException as exc:
                warnings.append(f"Could not inspect {node.container}: {exc}")
                containers.append(base | {"exists": False, "status": "inspect_failed", "health": None, "indicator": "red"})

        return containers, warnings

    def container_names(self) -> tuple[set[str] | None, str | None]:
        """Names of all containers known to Docker, for topology detection.

        One list call rather than a probe per marker container. Returns (None, warning)
        when Docker is unreachable so the caller can distinguish "nothing is running"
        from "we cannot tell".
        """
        try:
            client = self._docker()
            containers = client.containers.list(all=True)
        except DockerException as exc:
            self._client = None
            return None, f"Docker API unavailable for topology detection: {exc}"
        names: set[str] = set()
        for container in containers:
            if container.name:
                names.add(container.name)
        return names, None

    def amf_registration_events_seen(self) -> tuple[int | None, str | None]:
        try:
            client = self._docker()
            container = client.containers.get("oai-amf")
            if container.status != "running":
                return None, None
            logs = container.logs(tail=500).decode(errors="replace")
        except (DockerException, NotFound):
            return None, None
        count = len(re.findall(r"Registration accept|Registration Accept|5GMM-REGISTERED", logs, flags=re.I))
        return count, None
