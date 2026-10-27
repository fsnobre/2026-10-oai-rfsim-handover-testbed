"""Safe experiment actions: disabled-by-default gate, confirm requirement,
whitelisted argv, no-shell source assertions, runtime-check shape, and job
lifecycle (formerly validate_phase4)."""

import asyncio

import validate_phase4


def test_disabled_by_default():
    validate_phase4.validate_disabled_by_default()


def test_capabilities_disabled():
    validate_phase4.validate_capabilities_disabled()


def test_unknown_topology_rejected():
    validate_phase4.validate_unknown_topology_rejected()


def test_whitelisted_commands_and_no_shell():
    validate_phase4.validate_whitelisted_commands()


def test_runtime_checks_shape():
    validate_phase4.validate_runtime_checks_shape()


def test_disabled_request_rejected():
    asyncio.run(validate_phase4.validate_disabled_request_rejected())


def test_confirm_required():
    asyncio.run(validate_phase4.validate_confirm_required())


def test_success_failure_timeout_and_tails():
    asyncio.run(validate_phase4.validate_success_failure_timeout_and_tails())


def test_concurrency_guard():
    asyncio.run(validate_phase4.validate_concurrency_guard())


def test_terminate_process_group_helper():
    asyncio.run(validate_phase4.validate_terminate_process_group_helper())
