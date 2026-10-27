from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import signal
import subprocess
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from host_mounts import host_repo_root_status

# Actions that start or stop a docker compose stack. Their bind mounts are resolved by
# the host daemon, so they are refused when the repository root is not host-visible; see
# host_mounts.py. Telnet/ping-only actions are unaffected.
COMPOSE_SPAWNING_KINDS = {"deploy_topology", "teardown_topology", "smoke_test", "repeated_smoke_test"}

ALLOWED_SMOKE_TOPOLOGIES = {"f1", "n2-monolithic", "n2-cu-du"}
# trigger_handover.sh and measure_interruption.sh accept these topology args.
# usrp-cots has no handover, so it is intentionally excluded.
ALLOWED_HANDOVER_TOPOLOGIES = {"f1", "n2-monolithic", "n2-cu-du"}
# up.sh / down.sh accept these topology args (see scripts/lib.sh apply_topology).
# usrp-cots is included because the scripts accept it, but it needs a real radio.
ALLOWED_LIFECYCLE_TOPOLOGIES = {"f1", "n2-monolithic", "n2-cu-du", "usrp-cots"}
REPEATED_SMOKE_MIN_COUNT = 1
REPEATED_SMOKE_MAX_COUNT = 20
TAIL_LINES = 200
RECENT_JOB_LIMIT = 50
TERMINATION_GRACE_SECONDS = 5


class ActionError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(4)}"


def tail_append(lines: deque[str], chunk: bytes) -> None:
    text = chunk.decode(errors="replace")
    for line in text.splitlines():
        lines.append(line)


async def _stream_tail(reader: asyncio.StreamReader | None, lines: deque[str]) -> None:
    if reader is None:
        return
    while True:
        chunk = await reader.readline()
        if not chunk:
            return
        tail_append(lines, chunk)


@dataclass(frozen=True)
class ActionCommand:
    kind: str
    label: str
    argv: list[str]
    timeout_seconds: int
    env: dict[str, str] | None = None


def build_trigger_handover_command(repo_root: Path, topology: str, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_HANDOVER_TOPOLOGIES:
        raise ActionError(f"Unsupported handover topology: {topology}", status_code=400)
    return ActionCommand(
        kind="trigger_handover",
        label="scripts/trigger_handover.sh",
        argv=["bash", str(repo_root / "scripts" / "trigger_handover.sh"), topology],
        timeout_seconds=timeout_seconds,
    )


def build_measure_interruption_command(repo_root: Path, topology: str, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_HANDOVER_TOPOLOGIES:
        raise ActionError(f"Unsupported handover topology: {topology}", status_code=400)
    return ActionCommand(
        kind="measure_interruption",
        label="scripts/measure_interruption.sh",
        argv=["bash", str(repo_root / "scripts" / "measure_interruption.sh"), topology],
        timeout_seconds=timeout_seconds,
    )


def build_deploy_topology_command(repo_root: Path, topology: str, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_LIFECYCLE_TOPOLOGIES:
        raise ActionError(f"Unsupported deploy topology: {topology}", status_code=400)
    return ActionCommand(
        kind="deploy_topology",
        label="scripts/up.sh",
        argv=["bash", str(repo_root / "scripts" / "up.sh"), topology],
        timeout_seconds=timeout_seconds,
    )


def build_teardown_topology_command(repo_root: Path, topology: str, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_LIFECYCLE_TOPOLOGIES:
        raise ActionError(f"Unsupported teardown topology: {topology}", status_code=400)
    return ActionCommand(
        kind="teardown_topology",
        label="scripts/down.sh",
        argv=["bash", str(repo_root / "scripts" / "down.sh"), topology],
        timeout_seconds=timeout_seconds,
    )


def build_smoke_test_command(repo_root: Path, topology: str, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_SMOKE_TOPOLOGIES:
        raise ActionError(f"Unsupported smoke-test topology: {topology}", status_code=400)
    return ActionCommand(
        kind="smoke_test",
        label="scripts/run_smoke_test.sh",
        argv=["bash", str(repo_root / "scripts" / "run_smoke_test.sh"), topology],
        timeout_seconds=timeout_seconds,
    )


def build_repeated_smoke_test_command(repo_root: Path, topology: str, count: int, timeout_seconds: int) -> ActionCommand:
    if topology not in ALLOWED_SMOKE_TOPOLOGIES:
        raise ActionError(f"Unsupported repeated smoke-test topology: {topology}", status_code=400)
    if count < REPEATED_SMOKE_MIN_COUNT or count > REPEATED_SMOKE_MAX_COUNT:
        raise ActionError(
            f"Repeated smoke-test count must be between {REPEATED_SMOKE_MIN_COUNT} and {REPEATED_SMOKE_MAX_COUNT}",
            status_code=400,
        )
    return ActionCommand(
        kind="repeated_smoke_test",
        label="scripts/run_repeated_smoke_tests.sh",
        argv=["bash", str(repo_root / "scripts" / "run_repeated_smoke_tests.sh"), topology],
        timeout_seconds=timeout_seconds,
        env={"RUNS": str(count)},
    )


def action_runtime_checks(repo_root: Path) -> dict[str, bool]:
    return {
        "bash": shutil.which("bash") is not None,
        "docker": shutil.which("docker") is not None,
        "docker_compose": _docker_compose_available(),
        "nc": shutil.which("nc") is not None,
        "ip": shutil.which("ip") is not None,
        "ss": shutil.which("ss") is not None,
        "ping": shutil.which("ping") is not None,
        "docker_socket": Path("/var/run/docker.sock").exists(),
        "tun_device": Path("/dev/net/tun").exists(),
        "results_writable": (repo_root / "results").exists() and os.access(repo_root / "results", os.W_OK),
        "trigger_script_exists": (repo_root / "scripts" / "trigger_handover.sh").exists(),
        "measure_interruption_script_exists": (repo_root / "scripts" / "measure_interruption.sh").exists(),
        "smoke_script_exists": (repo_root / "scripts" / "run_smoke_test.sh").exists(),
        "repeated_smoke_script_exists": (repo_root / "scripts" / "run_repeated_smoke_tests.sh").exists(),
        "up_script_exists": (repo_root / "scripts" / "up.sh").exists(),
        "down_script_exists": (repo_root / "scripts" / "down.sh").exists(),
    }


def _docker_compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
    except Exception:
        return False
    return result.returncode == 0


def terminate_process_group(pid: int, sig: signal.Signals = signal.SIGTERM) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return


class ActionManager:
    def __init__(
        self,
        repo_root: Path,
        actions_enabled: bool,
        trigger_timeout_seconds: int,
        measure_interruption_timeout_seconds: int,
        smoke_timeout_seconds: int,
        repeated_smoke_timeout_seconds: int,
        deploy_timeout_seconds: int = 600,
        teardown_timeout_seconds: int = 300,
    ) -> None:
        self.repo_root = repo_root
        self.actions_enabled = actions_enabled
        self.trigger_timeout_seconds = trigger_timeout_seconds
        self.measure_interruption_timeout_seconds = measure_interruption_timeout_seconds
        self.smoke_timeout_seconds = smoke_timeout_seconds
        self.repeated_smoke_timeout_seconds = repeated_smoke_timeout_seconds
        self.deploy_timeout_seconds = deploy_timeout_seconds
        self.teardown_timeout_seconds = teardown_timeout_seconds
        self._jobs: dict[str, dict[str, Any]] = {}
        self._order: deque[str] = deque(maxlen=RECENT_JOB_LIMIT)
        self._tasks: set[asyncio.Task[None]] = set()
        self._repo_root_status: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    def capabilities(self) -> dict[str, Any]:
        disabled_reason = None if self.actions_enabled else "DASHBOARD_ENABLE_ACTIONS is not true"
        repo_root = self.repo_root_status()
        compose_reason = disabled_reason
        if self.actions_enabled and not repo_root["host_visible"]:
            compose_reason = "Repository root is not visible to the host Docker daemon"
        compose_enabled = self.actions_enabled and repo_root["host_visible"]
        return {
            "actions_enabled": self.actions_enabled,
            "environment": {
                "repo_root": repo_root["repo_root"],
                "host_path": repo_root["host_path"],
                "repo_root_host_visible": repo_root["host_visible"],
                "repo_root_verified": repo_root["verified"],
                "detail": repo_root["detail"],
            },
            "available_actions": [
                {
                    "kind": "trigger_handover",
                    "enabled": self.actions_enabled,
                    "reason": disabled_reason,
                    "allowed_topologies": sorted(ALLOWED_HANDOVER_TOPOLOGIES),
                },
                {
                    "kind": "measure_interruption",
                    "enabled": self.actions_enabled,
                    "reason": disabled_reason,
                    "allowed_topologies": sorted(ALLOWED_HANDOVER_TOPOLOGIES),
                },
                {
                    "kind": "smoke_test",
                    "enabled": compose_enabled,
                    "reason": compose_reason,
                    "allowed_topologies": sorted(ALLOWED_SMOKE_TOPOLOGIES),
                },
                {
                    "kind": "repeated_smoke_test",
                    "enabled": compose_enabled,
                    "reason": compose_reason,
                    "allowed_topologies": sorted(ALLOWED_SMOKE_TOPOLOGIES),
                    "min_count": REPEATED_SMOKE_MIN_COUNT,
                    "max_count": REPEATED_SMOKE_MAX_COUNT,
                },
                {
                    "kind": "deploy_topology",
                    "enabled": compose_enabled,
                    "reason": compose_reason,
                    "allowed_topologies": sorted(ALLOWED_LIFECYCLE_TOPOLOGIES),
                },
                {
                    "kind": "teardown_topology",
                    "enabled": compose_enabled,
                    "reason": compose_reason,
                    "allowed_topologies": sorted(ALLOWED_LIFECYCLE_TOPOLOGIES),
                },
            ],
            "safety": {
                "arbitrary_commands": False,
                "config_editing": False,
                "container_lifecycle": False,
                "shell_execution": False,
                "single_job_concurrency": True,
                "bounded_output_tails": True,
            },
            "runtime_checks": {
                **action_runtime_checks(self.repo_root),
                "repo_root_host_visible": repo_root["host_visible"],
            },
        }

    def jobs(self, include_tails: bool = True) -> list[dict[str, Any]]:
        return [self._job_view(self._jobs[job_id], include_tails=include_tails) for job_id in reversed(self._order)]

    def job(self, job_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        return self._job_view(job, include_tails=True) if job else None

    def actions_summary(self) -> dict[str, Any]:
        running = self.running_job()
        return {
            "enabled": self.actions_enabled,
            "running_job": self._job_view(running, include_tails=False) if running else None,
            "recent_jobs": self.jobs(include_tails=False)[:10],
        }

    def running_job(self) -> dict[str, Any] | None:
        for job in self._jobs.values():
            if job.get("status") in {"queued", "running"}:
                return job
        return None

    async def start_trigger_handover(self, confirm: bool, topology: str) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_trigger_handover_command(self.repo_root, topology, self.trigger_timeout_seconds)
        return await self._start(command)

    async def start_measure_interruption(self, confirm: bool, topology: str) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_measure_interruption_command(self.repo_root, topology, self.measure_interruption_timeout_seconds)
        return await self._start(command)

    async def start_deploy_topology(self, confirm: bool, topology: str) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_deploy_topology_command(self.repo_root, topology, self.deploy_timeout_seconds)
        return await self._start(command)

    async def start_teardown_topology(self, confirm: bool, topology: str) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_teardown_topology_command(self.repo_root, topology, self.teardown_timeout_seconds)
        return await self._start(command)

    async def start_smoke_test(self, confirm: bool, topology: str) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_smoke_test_command(self.repo_root, topology, self.smoke_timeout_seconds)
        return await self._start(command)

    async def start_repeated_smoke_test(self, confirm: bool, topology: str, count: int) -> dict[str, Any]:
        if not confirm:
            raise ActionError("confirm must be true", status_code=400)
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        command = build_repeated_smoke_test_command(
            self.repo_root,
            topology,
            count,
            self.repeated_smoke_timeout_seconds,
        )
        return await self._start(command)

    def repo_root_status(self) -> dict[str, Any]:
        """Cached: the mount layout cannot change without restarting the backend."""
        if self._repo_root_status is None:
            self._repo_root_status = host_repo_root_status(self.repo_root)
        return self._repo_root_status

    def _require_host_visible_repo_root(self, kind: str) -> None:
        if kind not in COMPOSE_SPAWNING_KINDS:
            return
        status = self.repo_root_status()
        if status["host_visible"]:
            return
        raise ActionError(status["detail"], 409)

    async def _start(self, command: ActionCommand) -> dict[str, Any]:
        if not self.actions_enabled:
            raise ActionError("Actions are disabled. Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled experiment actions.", 403)
        self._require_host_visible_repo_root(command.kind)
        async with self._lock:
            if self.running_job():
                raise ActionError("Another dashboard action job is already running.", 409)
            job = self._new_job(command)
            self._jobs[job["job_id"]] = job
            self._evict_overflow(self._order, job["job_id"])
            # Hold a strong reference until the task completes: asyncio keeps only a weak
            # one, so an unreferenced task can be garbage-collected mid-run (a long smoke
            # test is exactly the kind of job at risk).
            task = asyncio.create_task(self._run_job(job, command))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return self._job_view(job, include_tails=True)

    def _evict_overflow(self, order: deque[str], job_id: str) -> None:
        """Append to the bounded order deque, dropping any job it evicts from the job
        map too. Without this, ``_jobs`` grows for the process lifetime and evicted jobs
        stay fetchable by ID while absent from the listing."""
        evicted = order[0] if len(order) == order.maxlen else None
        order.append(job_id)
        if evicted is not None and evicted not in order:
            self._jobs.pop(evicted, None)

    def _new_job(self, command: ActionCommand) -> dict[str, Any]:
        return {
            "job_id": new_job_id(),
            "kind": command.kind,
            "status": "queued",
            "command_label": command.label,
            "started_at": None,
            "finished_at": None,
            "returncode": None,
            "stdout_tail": deque(maxlen=TAIL_LINES),
            "stderr_tail": deque(maxlen=TAIL_LINES),
            "warnings": [],
            "timeout_seconds": command.timeout_seconds,
            "metadata": {"env": dict(command.env or {})},
        }

    async def _run_job(self, job: dict[str, Any], command: ActionCommand) -> None:
        job["status"] = "running"
        job["started_at"] = utc_now()
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command.argv,
                cwd=str(self.repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                env={**os.environ, **(command.env or {})},
            )
            stdout_task = asyncio.create_task(_stream_tail(process.stdout, job["stdout_tail"]))
            stderr_task = asyncio.create_task(_stream_tail(process.stderr, job["stderr_tail"]))
            try:
                await asyncio.wait_for(process.wait(), timeout=command.timeout_seconds)
            except asyncio.TimeoutError:
                job["warnings"].append(f"Action timed out after {command.timeout_seconds} seconds.")
                terminate_process_group(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=TERMINATION_GRACE_SECONDS)
                except asyncio.TimeoutError:
                    job["warnings"].append("Action did not exit after SIGTERM; sent SIGKILL to process group.")
                    terminate_process_group(process.pid, signal.SIGKILL)
                    await process.wait()
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
                job["status"] = "timed_out"
                job["returncode"] = process.returncode
                return

            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            job["returncode"] = process.returncode
            job["status"] = "succeeded" if process.returncode == 0 else "failed"
        except Exception as exc:
            job["status"] = "failed"
            job["warnings"].append(f"Action runner failed: {exc}")
            if process is not None and process.returncode is not None:
                job["returncode"] = process.returncode
        finally:
            job["finished_at"] = utc_now()

    def _job_view(self, job: dict[str, Any] | None, include_tails: bool) -> dict[str, Any]:
        if job is None:
            return {}
        view = {
            "job_id": job["job_id"],
            "kind": job["kind"],
            "status": job["status"],
            "command_label": job["command_label"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "returncode": job["returncode"],
            "warnings": list(job["warnings"]),
            "timeout_seconds": job["timeout_seconds"],
            "metadata": job.get("metadata", {}),
        }
        if include_tails:
            view["stdout_tail"] = list(job["stdout_tail"])
            view["stderr_tail"] = list(job["stderr_tail"])
        return view
