from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from time import monotonic
from typing import Any


def parse_supported_commands(help_text: str) -> list[str]:
    commands: set[str] = set()
    for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]*(?:\s+stats)?\b", help_text):
        cleaned = " ".join(token.lower().split())
        if cleaned in {"help", "ue", "rrc stats", "mac stats", "stats"}:
            commands.add(cleaned)
    return sorted(commands)


def parse_attached_ues(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    ues: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not re.search(r"\b(ue|rnti|rrc)\b", line, flags=re.I):
            continue
        ue: dict[str, Any] = {"raw": line.strip()}
        rnti = re.search(r"rnti\s*[:=]?\s*(0x[0-9a-fA-F]+|\d+)", line, flags=re.I)
        rrc_id = re.search(r"(?:rrc(?:_ue)?_id|ue(?:\s+id)?)\s*[:=]?\s*(\d+)", line, flags=re.I)
        du = re.search(r"(?:du|du_id|serving_du)\s*[:=]?\s*([A-Za-z0-9_-]+)", line, flags=re.I)
        if rnti:
            ue["rnti"] = rnti.group(1)
        if rrc_id:
            ue["rrc_id"] = rrc_id.group(1)
        if du:
            ue["serving_du"] = du.group(1)
        if len(ue) > 1:
            ues.append(ue)
    if not ues and text.strip():
        warnings.append("CU telnet returned data, but no UE context could be parsed.")
    return ues, warnings


class TelnetPollerRegistry:
    """One poller per telnet endpoint, created on demand.

    The poller used to be hardwired to the F1 CU at 192.168.70.150, so an N2 topology was
    probed at the wrong address. Endpoints come from the topology registry
    (``TopologyConfig.primary_telnet_node``), and each endpoint keeps its own capability
    cache so switching topologies does not carry stale discovery across.
    """

    def __init__(self) -> None:
        self._pollers: dict[tuple[str, int], TelnetPoller] = {}

    def for_topology(self, topology: Any) -> TelnetPoller | None:
        node = topology.primary_telnet_node()
        if node is None or not node.telnet_host or not node.telnet_port:
            return None
        key = (node.telnet_host, node.telnet_port)
        if key not in self._pollers:
            self._pollers[key] = TelnetPoller(host=node.telnet_host, port=node.telnet_port)
        return self._pollers[key]

    @staticmethod
    def no_endpoint_state() -> dict[str, Any]:
        """State for a topology with no telnet control node, such as usrp-cots."""
        message = "This topology exposes no telnet control endpoint."
        return {
            "cu": {
                "enabled": False,
                "polling_enabled": False,
                "reachable": False,
                "host": None,
                "port": None,
                "last_checked": datetime.now(timezone.utc).isoformat(),
                "supported_commands": [],
                "raw_summary": None,
                "summary": message,
                "ue_count": None,
                "attached_ues": [],
                "warnings": [message],
                "warning": None,
            }
        }


class TelnetPoller:
    def __init__(
        self,
        host: str = "192.168.70.150",
        port: int = 9090,
        timeout_seconds: float = 1.5,
        poll_ttl_seconds: float = 5.0,
        capability_ttl_seconds: float = 300.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.poll_ttl_seconds = poll_ttl_seconds
        self.capability_ttl_seconds = capability_ttl_seconds
        self._last_poll_at = 0.0
        self._last_result: dict[str, Any] | None = None
        self._supported_commands: list[str] | None = None
        self._last_capability_at = 0.0

    def disabled_state(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        message = "Passive CU telnet polling is disabled; set DASHBOARD_ENABLE_TELNET_POLLING=true to enable it."
        return {
            "cu": {
                "enabled": False,
                "polling_enabled": False,
                "reachable": False,
                "host": self.host,
                "port": self.port,
                "last_checked": now,
                "supported_commands": [],
                "raw_summary": None,
                "summary": message,
                "ue_count": None,
                "attached_ues": [],
                "warnings": [message],
                "warning": None,
            }
        }

    async def _send_command(self, command: str) -> str:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.timeout_seconds,
        )
        writer.write(f"{command}\n".encode())
        await writer.drain()
        try:
            raw = await asyncio.wait_for(reader.read(8192), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            raw = b""
        writer.close()
        await writer.wait_closed()
        return raw.decode(errors="replace")

    async def poll(self) -> dict[str, Any]:
        now_monotonic = monotonic()
        if self._last_result is not None and now_monotonic - self._last_poll_at < self.poll_ttl_seconds:
            return self._last_result

        started = datetime.now(timezone.utc).isoformat()
        warnings: list[str] = []
        try:
            help_text = ""
            if self._supported_commands is None or now_monotonic - self._last_capability_at >= self.capability_ttl_seconds:
                help_text = await self._send_command("help")
                self._supported_commands = parse_supported_commands(help_text)
                self._last_capability_at = now_monotonic
            supported = self._supported_commands or []
            detail_text = ""
            if "rrc stats" in supported:
                detail_text = await self._send_command("rrc stats")
            elif "ue" in supported:
                detail_text = await self._send_command("ue")
            else:
                warnings.append("CU telnet is reachable, but no supported read-only UE context command was discovered.")
            attached_ues, parse_warnings = parse_attached_ues(detail_text)
            warnings.extend(parse_warnings)
            result = {
                "cu": {
                    "enabled": True,
                    "polling_enabled": True,
                    "reachable": True,
                    "host": self.host,
                    "port": self.port,
                    "last_checked": started,
                    "supported_commands": supported,
                    "raw_summary": (detail_text or help_text)[:2000],
                    "summary": (detail_text or help_text)[:1000],
                    "ue_count": len(attached_ues) if attached_ues else None,
                    "attached_ues": attached_ues,
                    "warnings": warnings,
                    "warning": "; ".join(warnings) if warnings else None,
                }
            }
            self._last_poll_at = now_monotonic
            self._last_result = result
            return result
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
            result = {
                "cu": {
                    "enabled": True,
                    "polling_enabled": True,
                    "reachable": False,
                    "host": self.host,
                    "port": self.port,
                    "last_checked": started,
                    "supported_commands": [],
                    "raw_summary": None,
                    "summary": None,
                    "ue_count": None,
                    "attached_ues": [],
                    "warnings": [f"CU telnet unreachable or changed output: {reason}"],
                    "warning": f"CU telnet unreachable or changed output: {reason}",
                }
            }
            self._last_poll_at = now_monotonic
            self._last_result = result
            return result
