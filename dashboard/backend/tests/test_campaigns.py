"""Campaign/repeated-run aggregation, statistics, outliers, host-path remap,
and repeated-action guards (formerly validate_phase5)."""

import asyncio

import validate_phase5


def test_empty_results():
    validate_phase5.test_empty_results()


def test_campaign_summary_and_outliers():
    validate_phase5.test_campaign_summary_and_outliers()


def test_statistics_ignore_nulls_and_are_deterministic():
    validate_phase5.test_statistics_ignore_nulls_and_are_deterministic()


def test_host_absolute_run_path_remaps_to_repo_root():
    validate_phase5.test_host_absolute_run_path_remaps_to_repo_root()


def test_malformed_artifacts_warn():
    validate_phase5.test_malformed_artifacts_warn()


def test_export_rows():
    validate_phase5.test_export_rows()


def test_repeated_action_guards():
    asyncio.run(validate_phase5.test_repeated_action_guards())
