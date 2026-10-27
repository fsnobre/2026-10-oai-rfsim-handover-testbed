from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import actions
from actions import (
    ALLOWED_HANDOVER_TOPOLOGIES,
    ALLOWED_LIFECYCLE_TOPOLOGIES,
    ALLOWED_SMOKE_TOPOLOGIES,
    TAIL_LINES,
    ActionCommand,
    ActionError,
    ActionManager,
    action_runtime_checks,
    build_deploy_topology_command,
    build_measure_interruption_command,
    build_repeated_smoke_test_command,
    build_smoke_test_command,
    build_teardown_topology_command,
    build_trigger_handover_command,
    terminate_process_group,
)
from config import DASHBOARD_ENABLE_ACTIONS


def manager(root: Path, enabled: bool = False) -> ActionManager:
    return ActionManager(
        root,
        actions_enabled=enabled,
        trigger_timeout_seconds=1,
        measure_interruption_timeout_seconds=1,
        smoke_timeout_seconds=1,
        repeated_smoke_timeout_seconds=1,
    )


def validate_disabled_by_default() -> None:
    assert DASHBOARD_ENABLE_ACTIONS is False


def validate_capabilities_disabled() -> None:
    caps = manager(Path("/tmp/nonexistent")).capabilities()
    assert caps["actions_enabled"] is False
    assert all(action["enabled"] is False for action in caps["available_actions"])
    assert caps["safety"]["arbitrary_commands"] is False
    assert caps["safety"]["shell_execution"] is False
    assert "runtime_checks" in caps


async def validate_disabled_request_rejected() -> None:
    try:
        await manager(Path("/tmp/nonexistent")).start_trigger_handover(confirm=True, topology="f1")
    except ActionError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("disabled action was not rejected")


async def validate_confirm_required() -> None:
    try:
        await manager(Path("/tmp/nonexistent"), enabled=True).start_trigger_handover(confirm=False, topology="f1")
    except ActionError as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("missing confirm was not rejected")


def validate_unknown_topology_rejected() -> None:
    try:
        build_smoke_test_command(Path("/repo"), "bad-topology", timeout_seconds=1)
    except ActionError as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("unsupported topology was not rejected")


def validate_whitelisted_commands() -> None:
    for topology in ALLOWED_HANDOVER_TOPOLOGIES:
        trigger = build_trigger_handover_command(Path("/repo"), topology, timeout_seconds=180)
        assert trigger.argv == ["bash", "/repo/scripts/trigger_handover.sh", topology]
        interruption = build_measure_interruption_command(Path("/repo"), topology, timeout_seconds=180)
        assert interruption.argv == ["bash", "/repo/scripts/measure_interruption.sh", topology]
    for builder in (build_trigger_handover_command, build_measure_interruption_command):
        try:
            builder(Path("/repo"), "bad-topology", timeout_seconds=180)
        except ActionError as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("unsupported handover topology was not rejected")
    for topology in ALLOWED_LIFECYCLE_TOPOLOGIES:
        deploy = build_deploy_topology_command(Path("/repo"), topology, timeout_seconds=600)
        assert deploy.argv == ["bash", "/repo/scripts/up.sh", topology]
        teardown = build_teardown_topology_command(Path("/repo"), topology, timeout_seconds=300)
        assert teardown.argv == ["bash", "/repo/scripts/down.sh", topology]
    for builder in (build_deploy_topology_command, build_teardown_topology_command):
        try:
            builder(Path("/repo"), "bad-topology", timeout_seconds=300)
        except ActionError as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("unsupported lifecycle topology was not rejected")
    for topology in ALLOWED_SMOKE_TOPOLOGIES:
        smoke = build_smoke_test_command(Path("/repo"), topology, timeout_seconds=900)
        assert smoke.argv == ["bash", "/repo/scripts/run_smoke_test.sh", topology]
        repeated = build_repeated_smoke_test_command(Path("/repo"), topology, count=2, timeout_seconds=3600)
        assert repeated.argv == ["bash", "/repo/scripts/run_repeated_smoke_tests.sh", topology]
        assert repeated.env == {"RUNS": "2"}
    source = Path(actions.__file__).read_text()
    assert "shell=True" not in source
    assert "create_subprocess_shell" not in source
    assert "start_new_session=True" in source
    assert "os.killpg" in source


def validate_runtime_checks_shape() -> None:
    checks = action_runtime_checks(Path("/tmp/nonexistent"))
    expected = {
        "bash",
        "docker",
        "docker_compose",
        "nc",
        "ip",
        "ss",
        "ping",
        "docker_socket",
        "tun_device",
        "results_writable",
        "trigger_script_exists",
        "measure_interruption_script_exists",
        "smoke_script_exists",
        "repeated_smoke_script_exists",
        "up_script_exists",
        "down_script_exists",
    }
    assert set(checks) == expected
    assert all(isinstance(value, bool) for value in checks.values())


async def validate_success_failure_timeout_and_tails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        mgr = manager(root, enabled=True)

        success = await mgr._start(  # noqa: SLF001 - direct validation of helper
            ActionCommand(
                kind="test_success",
                label="python-success",
                argv=[sys.executable, "-c", "print('ok')"],
                timeout_seconds=5,
            )
        )
        await _wait_finished(mgr, success["job_id"])
        job = mgr.job(success["job_id"])
        assert job["status"] == "succeeded"
        assert job["returncode"] == 0
        assert job["stdout_tail"] == ["ok"]

        failed = await mgr._start(  # noqa: SLF001
            ActionCommand(
                kind="test_failure",
                label="python-failure",
                argv=[sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"],
                timeout_seconds=5,
            )
        )
        await _wait_finished(mgr, failed["job_id"])
        job = mgr.job(failed["job_id"])
        assert job["status"] == "failed"
        assert job["returncode"] == 3

        timeout = await mgr._start(  # noqa: SLF001
            ActionCommand(
                kind="test_timeout",
                label="python-timeout",
                argv=[sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)']); print('start', flush=True); time.sleep(20)"],
                timeout_seconds=1,
            )
        )
        await _wait_finished(mgr, timeout["job_id"])
        job = mgr.job(timeout["job_id"])
        assert job["status"] == "timed_out"
        assert job["warnings"]

        many_lines = await mgr._start(  # noqa: SLF001
            ActionCommand(
                kind="test_tail",
                label="python-tail",
                argv=[sys.executable, "-c", "for i in range(250): print(f'line-{i}')"],
                timeout_seconds=5,
            )
        )
        await _wait_finished(mgr, many_lines["job_id"])
        job = mgr.job(many_lines["job_id"])
        assert len(job["stdout_tail"]) == TAIL_LINES
        assert job["stdout_tail"][0] == "line-50"
        assert job["stdout_tail"][-1] == "line-249"


async def validate_concurrency_guard() -> None:
    with TemporaryDirectory() as tmp:
        mgr = manager(Path(tmp), enabled=True)
        first = await mgr._start(  # noqa: SLF001
            ActionCommand(
                kind="long",
                label="python-long",
                argv=[sys.executable, "-c", "import time; time.sleep(2)"],
                timeout_seconds=5,
            )
        )
        try:
            await mgr._start(  # noqa: SLF001
                ActionCommand(
                    kind="second",
                    label="python-second",
                    argv=[sys.executable, "-c", "print('second')"],
                    timeout_seconds=5,
                )
            )
        except ActionError as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("second concurrent job was not rejected")
        await _wait_finished(mgr, first["job_id"])


async def validate_terminate_process_group_helper() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(20)",
        start_new_session=True,
    )
    terminate_process_group(process.pid, signal.SIGTERM)
    await asyncio.wait_for(process.wait(), timeout=5)
    assert process.returncode is not None
    terminate_process_group(process.pid, signal.SIGTERM)


async def _wait_finished(mgr: ActionManager, job_id: str) -> None:
    for _ in range(100):
        job = mgr.job(job_id)
        if job and job["status"] not in {"queued", "running"}:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"job did not finish: {job_id}")


async def async_main() -> None:
    await validate_disabled_request_rejected()
    await validate_confirm_required()
    await validate_success_failure_timeout_and_tails()
    await validate_concurrency_guard()
    await validate_terminate_process_group_helper()


def main() -> int:
    validate_disabled_by_default()
    validate_capabilities_disabled()
    validate_unknown_topology_rejected()
    validate_whitelisted_commands()
    validate_runtime_checks_shape()
    asyncio.run(async_main())
    print("Phase 4 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
