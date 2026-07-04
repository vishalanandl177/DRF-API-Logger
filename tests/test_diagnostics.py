"""
Tests for production diagnostics and doctor readiness checks.
"""
from unittest.mock import Mock, patch

from django.db.utils import OperationalError
from django.test import TestCase
from django.test.utils import override_settings


class DiagnosticsSettingsTests(TestCase):
    """Diagnostics should report configuration and runtime readiness clearly."""

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_reports_logging_disabled_warning(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF001",
            level="warning",
            message="DRF API Logger is disabled.",
        )

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    def test_signal_only_mode_skips_database_and_worker_checks(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()
        codes = {result.code for result in results}

        self.assert_result(
            results,
            code="DRF002",
            level="ok",
            message="Signal logging is enabled without database logging.",
        )
        self.assertFalse(codes.intersection({"DRF101", "DRF102", "DRF103", "DRF104", "DRF105", "DRF106"}))
        self.assertFalse(codes.intersection({"DRF201", "DRF202", "DRF203", "DRF204", "DRF205"}))

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_DEFAULT_DATABASE="missing")
    def test_database_alias_must_exist_when_database_logging_enabled(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF101",
            level="error",
            message='Configured log database alias "missing" is not available.',
        )

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch("drf_api_logger.diagnostics._database_table_exists", return_value=True)
    @patch("drf_api_logger.diagnostics._database_alias_available", return_value=True)
    @patch("drf_api_logger.diagnostics._has_pending_migrations", return_value=False)
    def test_database_ready_state_reports_alias_migrations_and_table(
        self,
        mock_pending,
        mock_alias,
        mock_table,
    ):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(results, code="DRF102", level="ok", message='Configured log database alias "default" is available.')
        self.assert_result(results, code="DRF104", level="ok", message="DRF API Logger migrations are applied.")
        self.assert_result(results, code="DRF105", level="ok", message="API log table is available.")

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch("drf_api_logger.diagnostics._database_table_exists", return_value=False)
    @patch("drf_api_logger.diagnostics._database_alias_available", return_value=True)
    @patch("drf_api_logger.diagnostics._has_pending_migrations", return_value=True)
    def test_database_not_ready_reports_pending_migrations_and_missing_table(
        self,
        mock_pending,
        mock_alias,
        mock_table,
    ):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF103",
            level="error",
            message="DRF API Logger migrations are not fully applied.",
        )
        self.assert_result(
            results,
            code="DRF106",
            level="error",
            message="API log table is missing.",
        )

    def test_database_helpers_use_real_connection_when_available(self):
        from drf_api_logger.diagnostics import (
            _database_table_exists,
            _has_pending_migrations,
        )

        self.assertTrue(_database_table_exists("default"))
        self.assertFalse(_has_pending_migrations("default"))

    def test_database_helpers_fail_closed_on_connection_errors(self):
        from drf_api_logger.diagnostics import (
            _database_table_exists,
            _has_pending_migrations,
        )

        class FailingConnections:
            def __getitem__(self, database):
                raise OperationalError("database unavailable")

        with patch("drf_api_logger.diagnostics.connections", FailingConnections()):
            self.assertFalse(_database_table_exists("default"))
            self.assertTrue(_has_pending_migrations("default"))

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch("drf_api_logger.diagnostics._database_table_exists", return_value=True)
    @patch("drf_api_logger.diagnostics._database_alias_available", return_value=True)
    @patch("drf_api_logger.diagnostics._has_pending_migrations", return_value=False)
    def test_reports_missing_background_worker(
        self,
        mock_pending,
        mock_alias,
        mock_table,
    ):
        from drf_api_logger import apps as logger_apps
        from drf_api_logger.diagnostics import run_diagnostics

        original_thread = logger_apps.LOGGER_THREAD
        logger_apps.LOGGER_THREAD = None
        try:
            results = run_diagnostics()
        finally:
            logger_apps.LOGGER_THREAD = original_thread

        self.assert_result(
            results,
            code="DRF202",
            level="warning",
            message="Background database worker is not available.",
        )

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch("drf_api_logger.diagnostics._database_table_exists", return_value=True)
    @patch("drf_api_logger.diagnostics._database_alias_available", return_value=True)
    @patch("drf_api_logger.diagnostics._has_pending_migrations", return_value=False)
    def test_reports_stopped_background_worker(
        self,
        mock_pending,
        mock_alias,
        mock_table,
    ):
        from drf_api_logger import apps as logger_apps
        from drf_api_logger.diagnostics import run_diagnostics

        worker = Mock()
        worker.is_alive.return_value = False
        worker.get_status.return_value = {"queue_backlog": 0}

        original_thread = logger_apps.LOGGER_THREAD
        logger_apps.LOGGER_THREAD = worker
        try:
            results = run_diagnostics()
        finally:
            logger_apps.LOGGER_THREAD = original_thread

        self.assert_result(
            results,
            code="DRF203",
            level="error",
            message="Background database worker is not running.",
        )

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch("drf_api_logger.diagnostics._database_table_exists", return_value=True)
    @patch("drf_api_logger.diagnostics._database_alias_available", return_value=True)
    @patch("drf_api_logger.diagnostics._has_pending_migrations", return_value=False)
    def test_reports_running_background_worker_and_risky_worker_stats(
        self,
        mock_pending,
        mock_alias,
        mock_table,
    ):
        from drf_api_logger import apps as logger_apps
        from drf_api_logger.diagnostics import run_diagnostics

        worker = Mock()
        worker.is_alive.return_value = True
        worker.get_status.return_value = {
            "queue_backlog": 251,
            "batch_size": 50,
            "interval": 10,
            "dropped_count": 1,
            "inserted_count": 20,
            "failed_insert_count": 2,
        }

        original_thread = logger_apps.LOGGER_THREAD
        logger_apps.LOGGER_THREAD = worker
        try:
            results = run_diagnostics()
        finally:
            logger_apps.LOGGER_THREAD = original_thread

        self.assert_result(
            results,
            code="DRF201",
            level="ok",
            message="Background database worker is running.",
        )
        self.assert_result(
            results,
            code="DRF204",
            level="warning",
            message="Background worker has failed insert attempts.",
        )
        self.assert_result(
            results,
            code="DRF205",
            level="warning",
            message="Background worker queue backlog is high.",
        )
        worker.get_status.assert_called_once()

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_LOGGER_QUEUE_MAX_SIZE=0,
        DRF_LOGGER_INTERVAL=0,
    )
    def test_reports_invalid_queue_settings(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF401",
            level="error",
            message="DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0.",
        )
        self.assert_result(
            results,
            code="DRF403",
            level="error",
            message="DRF_LOGGER_INTERVAL must be greater than 0.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE=-1,
        DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE=-1,
    )
    def test_warns_about_unbounded_payload_limits(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF301",
            level="warning",
            message="Request body logging is unbounded.",
        )
        self.assert_result(
            results,
            code="DRF302",
            level="warning",
            message="Response body logging is unbounded.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE="large",
        DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE="larger",
    )
    def test_reports_invalid_payload_limit_types(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF303",
            level="error",
            message="Request body size limit must be an integer.",
        )
        self.assert_result(
            results,
            code="DRF305",
            level="error",
            message="Response body size limit must be an integer.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_EXCLUDE_KEYS=[],
    )
    def test_warns_when_application_specific_masking_keys_are_empty(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF502",
            level="warning",
            message="No application-specific masking keys are configured.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_EXCLUDE_KEYS="token",
    )
    def test_reports_invalid_masking_key_type(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF501",
            level="error",
            message="DRF_API_LOGGER_EXCLUDE_KEYS must be a list or tuple.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SAMPLE_RATE=1.0,
    )
    def test_warns_when_profiling_every_logged_request(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF603",
            level="warning",
            message="Profiling is enabled for every logged request.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SAMPLE_RATE="all",
    )
    def test_reports_invalid_profiling_sample_rate(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF602",
            level="error",
            message="Profiling sample rate must be numeric.",
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SAMPLE_RATE=0.25,
    )
    def test_reports_limited_profiling_sample_rate_as_ok(self):
        from drf_api_logger.diagnostics import run_diagnostics

        results = run_diagnostics()

        self.assert_result(
            results,
            code="DRF604",
            level="ok",
            message="Profiling sample rate is limited.",
        )

    def test_result_summary_and_fail_level_helpers(self):
        from drf_api_logger.diagnostics import (
            DiagnosticResult,
            result_summary,
            results_as_dict,
            should_fail,
        )

        results = [
            DiagnosticResult("DRF900", "ok", "OK"),
            DiagnosticResult("DRF901", "warning", "Warning"),
            DiagnosticResult("DRF902", "error", "Error", details={"value": 1}),
        ]

        self.assertEqual(
            result_summary(results),
            {"level": "error", "ok": 1, "warning": 1, "error": 1},
        )
        self.assertEqual(results_as_dict(results)["results"][0]["details"], {})
        self.assertTrue(should_fail(results, "warning"))
        self.assertTrue(should_fail(results, "error"))
        self.assertFalse(should_fail(results[:2], "error"))
        self.assertFalse(should_fail(results, "ok"))

    def assert_result(self, results, code, level, message):
        matches = [
            result
            for result in results
            if result.code == code
            and result.level == level
            and result.message == message
        ]
        self.assertTrue(matches, "Missing diagnostic result {}".format(code))
