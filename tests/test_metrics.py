import json
import sys
import types
from unittest.mock import Mock, patch

from django.core.checks import ERROR, WARNING
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import Resolver404
from django.utils import timezone

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware


class FakeRecorder:
    def __init__(self):
        self.calls = []

    def observe_http_request(self, event):
        self.calls.append(("observe_http_request", event.copy()))

    def increment_active_requests(self, labels):
        self.calls.append(("increment_active_requests", labels.copy()))

    def decrement_active_requests(self, labels):
        self.calls.append(("decrement_active_requests", labels.copy()))

    def increment_http_exception(self, event):
        self.calls.append(("increment_http_exception", event.copy()))

    def observe_logger_overhead(self, labels, duration_seconds):
        self.calls.append(("observe_logger_overhead", labels.copy(), duration_seconds))

    def observe_payload_capture(self, labels, location, duration_seconds):
        self.calls.append(("observe_payload_capture", labels.copy(), location, duration_seconds))

    def observe_masking(self, labels, location, duration_seconds):
        self.calls.append(("observe_masking", labels.copy(), location, duration_seconds))

    def observe_serialization(self, labels, duration_seconds):
        self.calls.append(("observe_serialization", labels.copy(), duration_seconds))

    def observe_enqueue(self, labels, duration_seconds):
        self.calls.append(("observe_enqueue", labels.copy(), duration_seconds))

    def increment_enqueued_logs(self, queue_name="default"):
        self.calls.append(("increment_enqueued_logs", queue_name))

    def increment_processed_logs(self, storage_backend, count):
        self.calls.append(("increment_processed_logs", storage_backend, count))

    def increment_dropped_logs(self, reason):
        self.calls.append(("increment_dropped_logs", reason))

    def increment_storage_write_failure(self, storage_backend, exception_class):
        self.calls.append(("increment_storage_write_failure", storage_backend, exception_class))

    def set_queue_depth(self, queue_name, depth):
        self.calls.append(("set_queue_depth", queue_name, depth))

    def set_queue_capacity(self, queue_name, capacity):
        self.calls.append(("set_queue_capacity", queue_name, capacity))

    def set_queue_utilization(self, queue_name, ratio):
        self.calls.append(("set_queue_utilization", queue_name, ratio))

    def set_worker_up(self, worker_name, up):
        self.calls.append(("set_worker_up", worker_name, up))

    def increment_worker_restart(self, worker_name):
        self.calls.append(("increment_worker_restart", worker_name))

    def observe_flush(self, storage_backend, duration_seconds, batch_size):
        self.calls.append(("observe_flush", storage_backend, duration_seconds, batch_size))

    def observe_storage_write(self, storage_backend, duration_seconds):
        self.calls.append(("observe_storage_write", storage_backend, duration_seconds))

    def observe_profiling(self, labels, profiling):
        self.calls.append(("observe_profiling", labels.copy(), profiling.copy()))

    def observe_security_event(self, signal):
        self.calls.append(("observe_security_event", signal))

    def observe_security_detection(self, labels, duration_seconds):
        self.calls.append(("observe_security_detection", labels.copy(), duration_seconds))

    def increment_security_detection_error(self, rule_id, exception_class):
        self.calls.append(("increment_security_detection_error", rule_id, exception_class))


class MetricsSettingsAndLabelsTests(TestCase):
    @override_settings(DRF_API_LOGGER_METRICS_ENABLED=False)
    def test_disabled_metrics_return_noop_recorder(self):
        from drf_api_logger.metrics.recorder import get_recorder

        recorder = get_recorder()

        self.assertEqual(recorder.__class__.__name__, "NoOpMetricsRecorder")
        with recorder.timer("payload_capture", labels={"location": "request"}):
            pass

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="prometheus",
    )
    @patch(
        "drf_api_logger.metrics.prometheus.get_prometheus_recorder",
        side_effect=ImportError("missing prometheus_client"),
    )
    def test_missing_prometheus_runtime_returns_noop_recorder(self, mock_prometheus):
        from drf_api_logger.metrics.recorder import get_recorder

        recorder = get_recorder()

        self.assertEqual(recorder.__class__.__name__, "NoOpMetricsRecorder")

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_LABELS=[
            "method",
            "route",
            "status_class",
            "request_id",
            "client_ip",
        ],
    )
    def test_metric_label_builder_rejects_unsafe_configured_labels(self):
        from drf_api_logger.metrics.labels import build_http_labels

        labels = build_http_labels(
            {
                "method": "get",
                "status_code": 200,
                "raw_path": "/api/users/123/?token=secret",
                "client_ip": "203.0.113.20",
                "request_id": "req-123",
                "low_cardinality": {
                    "route": "api/users/<int:pk>/",
                    "status_class": "2xx",
                },
            }
        )

        self.assertEqual(labels["method"], "GET")
        self.assertEqual(labels["route"], "api/users/<int:pk>/")
        self.assertEqual(labels["status_class"], "2xx")
        self.assertNotIn("request_id", labels)
        self.assertNotIn("client_ip", labels)
        self.assertNotIn("raw_path", labels)

    def test_security_label_builder_uses_only_low_cardinality_values(self):
        from drf_api_logger.metrics.labels import build_security_labels
        from drf_api_logger.metrics.security import SecuritySignal

        signal = SecuritySignal(
            rule_id="DRFSEC-001",
            event_type="auth_failure",
            category="authentication",
            severity="warning",
            score=3,
            route="/api/private/123/",
            method="post",
            status_class="4xx",
            outcome="observed",
            reason="bad password for developer@example.invalid",
        )

        labels = build_security_labels(signal)

        self.assertEqual(labels["rule_id"], "DRFSEC-001")
        self.assertEqual(labels["category"], "authentication")
        self.assertEqual(labels["severity"], "warning")
        self.assertEqual(labels["route"], "/api/private/123/")
        self.assertEqual(labels["method"], "POST")
        self.assertEqual(labels["status_class"], "4xx")
        self.assertEqual(labels["reason"], "unknown")

    def test_unresolved_routes_use_low_cardinality_unresolved_labels(self):
        from drf_api_logger.metrics.labels import build_low_cardinality_from_resolver

        labels = build_low_cardinality_from_resolver(None, status_code=404)

        self.assertEqual(labels["route"], "unresolved")
        self.assertEqual(labels["view_name"], "unresolved")
        self.assertEqual(labels["status_class"], "4xx")


class OptionalPrometheusRecorderTests(TestCase):
    def fake_prometheus_module(self):
        module = types.ModuleType("prometheus_client")

        class FakeCollectorRegistry:
            pass

        class FakeMetric:
            instances = []

            def __init__(self, *args, **kwargs):
                self.calls = []
                FakeMetric.instances.append(self)

            def labels(self, **labels):
                self.calls.append(("labels", labels))
                return self

            def inc(self, amount=1):
                self.calls.append(("inc", amount))

            def dec(self, amount=1):
                self.calls.append(("dec", amount))

            def observe(self, value):
                self.calls.append(("observe", value))

            def set(self, value):
                self.calls.append(("set", value))

        module.Counter = FakeMetric
        module.Gauge = FakeMetric
        module.Histogram = FakeMetric
        module.CollectorRegistry = FakeCollectorRegistry
        module.generate_latest = lambda registry: b"# fake metrics\n"
        module.FakeMetric = FakeMetric
        return module

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
        DRF_API_LOGGER_SECURITY_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="prometheus",
        DRF_API_LOGGER_METRICS_GROUPS=["logger", "pipeline", "profiling"],
    )
    def test_prometheus_recorder_records_supported_metric_groups_with_fake_client(self):
        fake_module = self.fake_prometheus_module()
        with patch.dict(sys.modules, {"prometheus_client": fake_module}):
            from drf_api_logger.metrics.prometheus import (
                generate_prometheus_latest,
                get_prometheus_recorder,
                reset_prometheus_recorder_for_tests,
            )
            from drf_api_logger.metrics.security import SecuritySignal

            reset_prometheus_recorder_for_tests()
            recorder = get_prometheus_recorder()

            recorder.increment_active_requests({"method": "GET", "route": "api/test/"})
            recorder.observe_http_request(
                {
                    "method": "GET",
                    "status_code": 200,
                    "execution_time": 0.05,
                    "request_body_size_bytes": 10,
                    "response_body_size_bytes": 20,
                    "is_slow": True,
                    "low_cardinality": {
                        "route": "api/test/",
                        "view_name": "tests.view",
                        "status_class": "2xx",
                    },
                }
            )
            recorder.decrement_active_requests({"method": "GET", "route": "api/test/"})
            recorder.increment_http_exception(
                {
                    "status_code": 500,
                    "exception_class": "ValueError",
                    "low_cardinality": {"route": "api/test/"},
                }
            )
            recorder.observe_logger_overhead(
                {"route": "api/test/", "logging_enabled": "true"},
                0.001,
            )
            recorder.observe_payload_capture({"location": "request"}, "request", 0.001)
            recorder.observe_masking({"location": "log_event"}, "log_event", 0.001)
            recorder.observe_serialization({"payload": "database_log"}, 0.001)
            recorder.observe_enqueue({"queue_name": "database"}, 0.001)
            recorder.increment_enqueued_logs("database")
            recorder.increment_processed_logs("database", 2)
            recorder.increment_dropped_logs("queue_error")
            recorder.increment_skipped_logs("policy")
            recorder.increment_storage_write_failure("database", "OperationalError")
            recorder.set_queue_depth("database", 3)
            recorder.set_queue_capacity("database", 50)
            recorder.set_queue_utilization("database", 0.06)
            recorder.set_worker_up("insert_log_into_database", True)
            recorder.increment_worker_restart("insert_log_into_database")
            recorder.observe_flush("database", 0.002, 2)
            recorder.observe_storage_write("database", 0.002)
            recorder.observe_profiling(
                {"route": "api/test/", "view_name": "tests.view"},
                {
                    "middleware_before_view": 0.001,
                    "view_and_serialization": 0.1,
                    "middleware_after_view": 0.001,
                    "sql": {
                        "total_time": 0.08,
                        "query_count": 12,
                        "duplicate_query_count": 4,
                    },
                },
            )
            recorder.observe_security_event(
                SecuritySignal(
                    rule_id="DRFSEC-001",
                    event_type="auth_failure",
                    category="authentication",
                    severity="warning",
                    score=3,
                    route="api/login/",
                    method="POST",
                    status_class="4xx",
                )
            )
            recorder.observe_security_detection({"route": "api/login/"}, 0.001)
            recorder.increment_security_detection_error("DRFSEC-001", "RuntimeError")

            self.assertEqual(generate_prometheus_latest(), b"# fake metrics\n")
            self.assertTrue(
                any(call[0] in {"inc", "observe", "set"} for metric in fake_module.FakeMetric.instances for call in metric.calls)
            )
            reset_prometheus_recorder_for_tests()


class MetricsStateTests(TestCase):
    def test_bounded_rolling_state_evicts_by_ttl_and_capacity(self):
        from drf_api_logger.metrics.state import BoundedRollingState

        state = BoundedRollingState(max_keys=2, ttl_seconds=10)

        self.assertEqual(state.increment("a", now=100), 1)
        self.assertEqual(state.increment("a", now=101), 2)
        self.assertEqual(state.increment("b", now=102), 1)
        self.assertEqual(state.increment("c", now=103), 1)
        self.assertEqual(state.get("a", now=104), 0)
        self.assertEqual(state.get("b", now=104), 1)
        self.assertEqual(state.get("b", now=200), 0)


class MetricsSystemCheckTests(TestCase):
    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="prometheus",
    )
    def test_metrics_enabled_without_prometheus_dependency_reports_error(self):
        from drf_api_logger.metrics.system_checks import check_metrics_configuration

        messages = check_metrics_configuration(None)

        self.assertIn("drf_api_logger.E701", [message.id for message in messages])
        self.assertIn(ERROR, [message.level for message in messages])

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_METRICS_LABELS=["method", "request_id"],
        DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED=True,
        DRF_API_LOGGER_SECURITY_METRICS_ENABLED=True,
        DRF_API_LOGGER_SECURITY_BODY_INSPECTION={
            "enabled": True,
            "max_body_bytes": -1,
            "inspect_request_body": True,
            "inspect_response_body": False,
        },
    )
    def test_unsafe_metrics_configuration_reports_checks(self):
        from drf_api_logger.metrics.system_checks import check_metrics_configuration

        messages = check_metrics_configuration(None)
        ids = [message.id for message in messages]

        self.assertIn("drf_api_logger.E702", ids)
        self.assertIn("drf_api_logger.W703", ids)
        self.assertIn("drf_api_logger.E704", ids)
        self.assertIn(WARNING, [message.level for message in messages])

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="prometheus",
    )
    @patch.dict("os.environ", {"WEB_CONCURRENCY": "4"}, clear=True)
    def test_prometheus_multiprocess_configuration_reports_warning(self):
        from drf_api_logger.metrics.system_checks import check_metrics_configuration

        messages = check_metrics_configuration(None)

        self.assertIn("drf_api_logger.W705", [message.id for message in messages])


class MetricsMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def get_response(self, request):
        return HttpResponse(
            json.dumps({"message": "ok"}),
            content_type="application/json",
            status=200,
        )

    def throttled_response(self, request):
        return HttpResponse(
            json.dumps({"detail": "throttled"}),
            content_type="application/json",
            status=429,
        )

    def not_found_response(self, request):
        return HttpResponse(
            json.dumps({"detail": "missing"}),
            content_type="application/json",
            status=404,
        )

    def unauthorized_response(self, request):
        return HttpResponse(
            json.dumps({"detail": "unauthorized"}),
            content_type="application/json",
            status=401,
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=False,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
        DRF_API_LOGGER_ENABLE_CORRELATION=True,
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_api_metrics_can_observe_without_database_or_signal_logging(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "test"
        mock_resolve.return_value.route = "api/test/"
        mock_resolve.return_value.func = self.get_response

        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get("/api/test/?token=secret")
        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        http_calls = [call for call in recorder.calls if call[0] == "observe_http_request"]
        self.assertEqual(len(http_calls), 1)
        event = http_calls[0][1]
        self.assertEqual(event["method"], "GET")
        self.assertEqual(event["status_code"], 200)
        self.assertEqual(event["low_cardinality"]["route"], "api/test/")
        self.assertEqual(event["low_cardinality"]["status_class"], "2xx")
        self.assertNotIn("token=secret", str(event))

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=False,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
        DRF_API_LOGGER_SLOW_API_ABOVE=0,
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_api_metrics_include_active_size_slow_and_throttle_signals(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "throttle"
        mock_resolve.return_value.route = "api/throttle/"
        mock_resolve.return_value.func = self.throttled_response

        middleware = APILoggerMiddleware(get_response=self.throttled_response)
        request = self.factory.post(
            "/api/throttle/?token=secret",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        response = middleware(request)

        self.assertEqual(response.status_code, 429)
        self.assertTrue(any(call[0] == "increment_active_requests" for call in recorder.calls))
        self.assertTrue(any(call[0] == "decrement_active_requests" for call in recorder.calls))
        http_event = [call[1] for call in recorder.calls if call[0] == "observe_http_request"][0]
        self.assertEqual(http_event["status_code"], 429)
        self.assertEqual(http_event["low_cardinality"]["status_class"], "4xx")
        self.assertGreater(http_event["request_body_size_bytes"], 0)
        self.assertGreater(http_event["response_body_size_bytes"], 0)
        self.assertTrue(http_event["is_slow"])
        self.assertEqual(http_event["throttle_scope"], "unknown")
        self.assertNotIn("token=secret", str(http_event))

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=False,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_api_metrics_record_exceptions_without_swallowing_them(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        def raises(request):
            raise ValueError("private detail")

        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "raises"
        mock_resolve.return_value.route = "api/raises/"
        mock_resolve.return_value.func = raises

        middleware = APILoggerMiddleware(get_response=raises)
        request = self.factory.get("/api/raises/")

        with self.assertRaises(ValueError):
            middleware(request)

        exception_events = [call[1] for call in recorder.calls if call[0] == "increment_http_exception"]
        self.assertEqual(len(exception_events), 1)
        self.assertEqual(exception_events[0]["exception_class"], "ValueError")
        self.assertEqual(exception_events[0]["low_cardinality"]["route"], "api/raises/")
        self.assertEqual(exception_events[0]["low_cardinality"]["status_class"], "5xx")
        self.assertNotIn("private detail", str(exception_events[0]))
        self.assertTrue(any(call[0] == "decrement_active_requests" for call in recorder.calls))

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_SECURITY_METRICS_ENABLED=True,
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_security_metrics_use_response_status_class_not_pre_response_unknown(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "unauthorized"
        mock_resolve.return_value.route = "api/unauthorized/"
        mock_resolve.return_value.func = self.unauthorized_response

        middleware = APILoggerMiddleware(get_response=self.unauthorized_response)
        request = self.factory.get("/api/unauthorized/")
        response = middleware(request)

        self.assertEqual(response.status_code, 401)
        security_calls = [call for call in recorder.calls if call[0] == "observe_security_event"]
        self.assertGreaterEqual(len(security_calls), 1)
        self.assertTrue(all(call[1].status_class == "4xx" for call in security_calls))

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=False,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_METRICS_GROUPS=["profiling"],
        DRF_API_LOGGER_API_METRICS_ENABLED=True,
        DRF_API_LOGGER_SECURITY_METRICS_ENABLED=True,
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_unresolved_routes_do_not_emit_unknown_route_or_view_labels(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.side_effect = Resolver404({"path": "/favicon.ico"})

        middleware = APILoggerMiddleware(get_response=self.not_found_response)
        request = self.factory.get("/favicon.ico")
        response = middleware(request)

        self.assertEqual(response.status_code, 404)

        http_event = [call[1] for call in recorder.calls if call[0] == "observe_http_request"][0]
        self.assertEqual(http_event["low_cardinality"]["route"], "unresolved")
        self.assertEqual(http_event["low_cardinality"]["view_name"], "unresolved")
        self.assertEqual(http_event["low_cardinality"]["status_class"], "4xx")

        profiling_labels = [call[1] for call in recorder.calls if call[0] == "observe_profiling"][0]
        self.assertEqual(profiling_labels["route"], "unresolved")
        self.assertEqual(profiling_labels["view_name"], "unresolved")

        detection_labels = [call[1] for call in recorder.calls if call[0] == "observe_security_detection"][0]
        self.assertEqual(detection_labels["route"], "unresolved")

        security_signals = [call[1] for call in recorder.calls if call[0] == "observe_security_event"]
        self.assertTrue(security_signals)
        self.assertTrue(all(signal.route == "unresolved" for signal in security_signals))

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_METRICS_GROUPS=["profiling"],
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_profiling_metrics_emit_when_profiling_data_exists(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "profiled"
        mock_resolve.return_value.route = "api/profiled/"
        mock_resolve.return_value.func = self.get_response

        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get("/api/profiled/")
        middleware(request)

        profiling_calls = [call for call in recorder.calls if call[0] == "observe_profiling"]
        self.assertEqual(len(profiling_calls), 1)
        self.assertEqual(profiling_calls[0][1]["route"], "api/profiled/")
        self.assertIn("view_and_serialization", profiling_calls[0][2])

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
        DRF_API_LOGGER_SECURITY_METRICS_ENABLED=True,
        DRF_API_LOGGER_SECURITY_BODY_INSPECTION={
            "enabled": True,
            "max_body_bytes": 64,
            "inspect_request_body": True,
            "inspect_response_body": False,
        },
    )
    @patch("drf_api_logger.middleware.api_logger_middleware.get_recorder")
    @patch("drf_api_logger.middleware.api_logger_middleware.resolve")
    def test_security_detection_records_bounded_payload_signal(
        self,
        mock_resolve,
        mock_get_recorder,
    ):
        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = "tests"
        mock_resolve.return_value.url_name = "test"
        mock_resolve.return_value.route = "api/test/"
        mock_resolve.return_value.func = self.get_response

        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"search": "' OR 1=1 --", "password": "secret"}),
            content_type="application/json",
        )
        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        security_calls = [call for call in recorder.calls if call[0] == "observe_security_event"]
        self.assertGreaterEqual(len(security_calls), 1)
        signal = security_calls[0][1]
        self.assertEqual(signal.rule_id, "DRFSEC-006")
        self.assertEqual(signal.category, "payload")
        self.assertNotIn("secret", str(signal))
        self.assertNotIn("' OR 1=1", str(signal))


class BackgroundPipelineMetricsTests(TestCase):
    def log_data(self):
        return {
            "api": "/api/test/",
            "method": "GET",
            "status_code": 200,
            "headers": "{}",
            "body": "",
            "response": "{}",
            "client_ip_address": "127.0.0.1",
            "execution_time": 0.1,
            "added_on": timezone.now(),
        }

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
    )
    @patch("drf_api_logger.insert_log_into_database.get_recorder")
    @patch("drf_api_logger.insert_log_into_database.APILogsModel")
    def test_queue_enqueue_updates_pipeline_metrics(self, mock_model, mock_get_recorder):
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase

        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        thread = InsertLogIntoDatabase()

        thread.put_log_data(self.log_data())

        self.assertIn(("increment_enqueued_logs", "database"), recorder.calls)
        self.assertIn(("set_queue_depth", "database", 1), recorder.calls)
        self.assertIn(("set_queue_capacity", "database", 50), recorder.calls)
        self.assertTrue(any(call[0] == "set_queue_utilization" for call in recorder.calls))
        self.assertTrue(any(call[0] == "observe_enqueue" for call in recorder.calls))

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="none",
    )
    @patch("drf_api_logger.insert_log_into_database.get_recorder")
    @patch("drf_api_logger.insert_log_into_database.APILogsModel")
    def test_bulk_insert_updates_processed_and_flush_metrics(self, mock_model, mock_get_recorder):
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase

        recorder = FakeRecorder()
        mock_get_recorder.return_value = recorder
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.return_value = None

        thread = InsertLogIntoDatabase()
        thread._insert_into_data_base([Mock(), Mock()])

        self.assertIn(("increment_processed_logs", "database", 2), recorder.calls)
        self.assertTrue(any(call[0] == "observe_flush" for call in recorder.calls))
        self.assertTrue(any(call[0] == "observe_storage_write" for call in recorder.calls))


class SecurityRuleTests(TestCase):
    def setUp(self):
        from drf_api_logger.metrics.rules import reset_security_rule_state_for_tests

        reset_security_rule_state_for_tests()

    def test_security_rules_are_detect_only_and_do_not_expose_payload_values(self):
        from drf_api_logger.metrics.security import SecurityContext, evaluate_security_signals

        context = SecurityContext(
            request=None,
            response=None,
            exception=None,
            route="api/login/",
            method="POST",
            status_code=401,
            status_class="4xx",
            request_body_sample=b'{"password": "secret", "q": "<script>alert(1)</script>"}',
            response_body_sample=None,
            actor_fingerprint="actor-hmac",
            low_cardinality={"route": "api/login/", "status_class": "4xx"},
            business_context={},
        )

        signals = evaluate_security_signals(context)

        self.assertTrue(any(signal.rule_id == "DRFSEC-001" for signal in signals))
        self.assertTrue(any(signal.rule_id == "DRFSEC-006" for signal in signals))
        self.assertTrue(all(signal.outcome == "observed" for signal in signals))
        self.assertNotIn("secret", str(signals))
        self.assertNotIn("<script>", str(signals))

    @override_settings(
        DRF_API_LOGGER_SECURITY_RULES={
            "auth_abuse": True,
            "token_abuse": True,
            "route_scan": True,
            "admin_probe": True,
            "object_id_enumeration": True,
            "payload_attack_patterns": True,
            "resource_abuse": True,
            "data_exfiltration": True,
            "business_logic_hooks": True,
        }
    )
    def test_security_registry_emits_all_rule_ids_with_bounded_state(self):
        from drf_api_logger.metrics.security import SecurityContext, evaluate_security_signals

        def context(**overrides):
            request = Mock()
            request.path = overrides.pop("path", "/api/orders/123/")
            request.GET = overrides.pop("query", {})
            values = {
                "request": request,
                "response": None,
                "exception": None,
                "route": "api/orders/<int:pk>/",
                "method": "GET",
                "status_code": 200,
                "status_class": "2xx",
                "request_body_sample": None,
                "response_body_sample": None,
                "actor_fingerprint": "actor-hmac",
                "low_cardinality": {"route": "api/orders/<int:pk>/", "status_class": "2xx"},
                "business_context": {},
            }
            values.update(overrides)
            return SecurityContext(**values)

        signals = []
        signals += evaluate_security_signals(context(route="api/login/", method="POST", status_code=401, status_class="4xx"))
        signals += evaluate_security_signals(context(route="api/login/", method="POST", status_code=401, status_class="4xx"))
        signals += evaluate_security_signals(context(route="api/login/", method="POST", status_code=401, status_class="4xx"))
        signals += evaluate_security_signals(context(route="api/login/", method="POST", status_code=200, status_class="2xx"))
        signals += evaluate_security_signals(context(route="api/token/", method="POST", status_code=401, status_class="4xx"))
        signals += evaluate_security_signals(context(route="api/private/", status_code=403, status_class="4xx"))
        signals += evaluate_security_signals(context(route="admin/login/", path="/admin/login/", status_code=404, status_class="4xx"))
        signals += evaluate_security_signals(context(request_body_sample=b"<script>alert(1)</script>"))
        signals += evaluate_security_signals(context(status_code=429, status_class="4xx"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/missing-a/"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/missing-b/"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/missing-c/"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/orders/1/"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/orders/2/"))
        signals += evaluate_security_signals(context(status_code=404, status_class="4xx", path="/api/orders/3/"))
        signals += evaluate_security_signals(context(request_body_sample=b"hello\nworld"))
        signals += evaluate_security_signals(context(response_body_sample=b'{"api_key": "secret"}'))
        signals += evaluate_security_signals(context(query={"page": "1"}))
        signals += evaluate_security_signals(context(query={"page": "2"}))
        signals += evaluate_security_signals(context(query={"page": "3"}))
        signals += evaluate_security_signals(context(route="api/export/", response_body_sample=b"x" * 8192))
        signals += evaluate_security_signals(context(response_body_sample=b"x" * 8192))
        signals += evaluate_security_signals(
            context(
                business_context={
                    "is_sensitive_route": True,
                    "flow_name": "checkout",
                    "business_action": "payment_attempted",
                }
            )
        )
        signals += evaluate_security_signals(
            context(
                business_context={
                    "flow_name": "checkout",
                    "business_action": "payment_attempted",
                }
            )
        )
        signals += evaluate_security_signals(
            context(
                business_context={
                    "flow_name": "checkout",
                    "business_action": "payment_attempted",
                }
            )
        )

        rule_ids = {signal.rule_id for signal in signals}
        self.assertEqual(rule_ids, {"DRFSEC-%03d" % index for index in range(1, 17)})
        self.assertNotIn("secret", str(signals))


class MetricsEndpointTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED=False)
    def test_metrics_endpoint_is_disabled_by_default(self):
        from drf_api_logger.metrics.views import prometheus_metrics_view

        with self.assertRaises(Http404):
            prometheus_metrics_view(self.factory.get("/metrics/"))

    @override_settings(
        DRF_API_LOGGER_METRICS_ENABLED=True,
        DRF_API_LOGGER_METRICS_EXPORTER="prometheus",
        DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED=True,
    )
    @patch("drf_api_logger.metrics.views.generate_prometheus_latest", return_value=b"# HELP test\n")
    def test_metrics_endpoint_returns_prometheus_text_when_enabled(self, mock_generate):
        from drf_api_logger.metrics.views import prometheus_metrics_view

        response = prometheus_metrics_view(self.factory.get("/metrics/"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(response.content, b"# HELP test\n")
