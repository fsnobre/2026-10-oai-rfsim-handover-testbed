from __future__ import annotations

import asyncio
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any

RTT_RE = re.compile(r"time[=<](?P<rtt>\d+(?:\.\d+)?)\s*ms", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ping_rtt(output: str) -> float | None:
    match = RTT_RE.search(output or "")
    if not match:
        return None
    try:
        return float(match.group("rtt"))
    except ValueError:
        return None


class LiveLatencyMonitor:
    """Bounded live ICMP probe history for the Overview handover gap chart."""

    def __init__(
        self,
        *,
        container: str = "oai-nr-ue",
        interface: str = "oaitun_ue1",
        target: str = "192.168.71.135",
        retention: int = 300,
        min_interval_seconds: float = 0.9,
        timeout_seconds: float = 2.5,
    ) -> None:
        self.container = container
        self.interface = interface
        self.target = target
        self.retention = retention
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self._samples: deque[dict[str, Any]] = deque(maxlen=retention)
        self._last_monotonic = 0.0
        self._active_container = container
        self._skip_reason: str | None = None

    def _resolve_skip(self, containers: list[dict[str, Any]] | None, topology: Any) -> str | None:
        """Why probing is not possible right now, or None if it is.

        Without this the monitor spawned a failing ``docker exec`` every second whenever
        the testbed was down — the state the dashboard is explicitly expected to survive —
        and on usrp-cots, where there is no UE container at all (the UE is a COTS handset).
        """
        if topology is not None:
            node = topology.ue_node()
            if node is None:
                return f"{topology.name} has no UE container to probe from."
            self._active_container = node.container

        if containers is None:
            return None

        item = next((entry for entry in containers if entry.get("name") == self._active_container), None)
        if item is None:
            return f"UE container {self._active_container} is not part of the current topology."
        if item.get("status") != "running":
            return f"UE container {self._active_container} is not running ({item.get('status') or 'unknown'})."
        return None

    async def sample(
        self,
        containers: list[dict[str, Any]] | None = None,
        topology: Any = None,
    ) -> dict[str, Any] | None:
        self._skip_reason = self._resolve_skip(containers, topology)
        if self._skip_reason is not None:
            # Drop stale samples rather than leaving a chart that looks live but is not.
            self._samples.clear()
            return None

        now = asyncio.get_running_loop().time()
        if self._samples and now - self._last_monotonic < self.min_interval_seconds:
            return self._samples[-1]
        self._last_monotonic = now

        command = [
            "docker",
            "exec",
            self._active_container,
            "ping",
            "-I",
            self.interface,
            "-c",
            "1",
            "-W",
            "1",
            self.target,
        ]
        timestamp = utc_now()
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
            except TimeoutError:
                process.kill()
                await process.wait()
                sample = self._make_sample(timestamp, False, None, "timeout", "ping probe timed out")
                self._samples.append(sample)
                return sample
        except FileNotFoundError:
            sample = self._make_sample(timestamp, False, None, "unavailable", "docker CLI is not available")
            self._samples.append(sample)
            return sample
        except OSError as exc:
            sample = self._make_sample(timestamp, False, None, "error", str(exc)[:180])
            self._samples.append(sample)
            return sample

        text = stdout.decode(errors="replace") + "\n" + stderr.decode(errors="replace")
        rtt_ms = parse_ping_rtt(text)
        reachable = process.returncode == 0 and rtt_ms is not None
        status = "delivered" if reachable else "lost"
        error = None if reachable else _short_error(text, process.returncode)
        sample = self._make_sample(timestamp, reachable, rtt_ms, status, error)
        self._samples.append(sample)
        return sample

    def state(self) -> dict[str, Any]:
        samples = list(self._samples)
        delivered = sum(1 for item in samples if item.get("reachable"))
        lost = sum(1 for item in samples if item.get("reachable") is False)
        latest = samples[-1] if samples else None
        if self._skip_reason is not None:
            warnings = [self._skip_reason]
        elif samples:
            warnings = []
        else:
            warnings = ["No live latency samples have been collected yet."]
        return {
            "container": self._active_container,
            "interface": self.interface,
            "target": self.target,
            "source": "docker_exec_ping",
            "retention_samples": self.retention,
            "probing": self._skip_reason is None,
            "skip_reason": self._skip_reason,
            "latest": latest,
            "samples": samples,
            "delivered_count": delivered,
            "lost_count": lost,
            "warnings": warnings,
        }

    def _make_sample(
        self,
        timestamp: str,
        reachable: bool,
        rtt_ms: float | None,
        status: str,
        error: str | None,
    ) -> dict[str, Any]:
        label = timestamp.split("T", 1)[-1].replace("Z", "")[:8]
        return {
            "timestamp": timestamp,
            "label": label,
            "reachable": reachable,
            "rtt_ms": rtt_ms,
            "status": status,
            "error": error,
        }


def _short_error(text: str, returncode: int | None) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if lines:
        return lines[-1][:180]
    return f"ping exited with return code {returncode}"
