from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import resolve

from drf_api_logger.correlation import (
    build_correlation_context,
    build_low_cardinality_metadata,
    get_header_value,
    parse_traceparent,
    sanitize_correlation_id,
)
from drf_api_logger.logging_context import (
    clear_correlation_context,
    get_correlation_context,
    set_correlation_context,
)


def context_from_request(request):
    return {
        "actor_id": "actor_123",
        "tenant_id": "tenant_456",
        "api_consumer_id": "consumer_789",
        "client_id": "client_abc",
        "username": "must_not_be_persisted",
    }


class CorrelationHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sanitize_correlation_id_accepts_safe_values(self):
        self.assertEqual(sanitize_correlation_id("req-123_ABC"), "req-123_ABC")
        self.assertEqual(sanitize_correlation_id("trace:abc/123"), "trace:abc/123")

    def test_sanitize_correlation_id_rejects_unsafe_values(self):
        self.assertIsNone(sanitize_correlation_id(""))
        self.assertIsNone(sanitize_correlation_id("abc def"))
        self.assertIsNone(sanitize_correlation_id("x" * 129))
        self.assertIsNone(sanitize_correlation_id("Bearer secret-token"))
        self.assertIsNone(sanitize_correlation_id("line\nbreak"))

    def test_parse_traceparent_extracts_trace_id(self):
        header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        self.assertEqual(parse_traceparent(header), "4bf92f3577b34da6a3ce929d0e0e4736")

    def test_parse_traceparent_rejects_invalid_trace_id(self):
        self.assertIsNone(parse_traceparent("00-00000000000000000000000000000000-00f067aa0ba902b7-01"))
        self.assertIsNone(parse_traceparent("invalid"))

    def test_get_header_value_accepts_django_meta_and_header_style_names(self):
        headers = {
            "X_REQUEST_ID": "req-1",
            "TRACEPARENT": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        }
        self.assertEqual(get_header_value(headers, ["X-Request-ID"]), "req-1")
        self.assertEqual(get_header_value(headers, ["traceparent"]), headers["TRACEPARENT"])

    @override_settings(
        DRF_API_LOGGER_ENABLE_CORRELATION=True,
        DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC="tests.test_correlation.context_from_request",
    )
    def test_build_context_includes_safe_ids_route_metadata_and_opaque_context(self):
        request = self.factory.get(
            "/api/test/",
            HTTP_X_REQUEST_ID="req-123",
            HTTP_TRACEPARENT="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        )
        resolver_match = resolve("/api/test/")
        headers = {
            "X_REQUEST_ID": "req-123",
            "TRACEPARENT": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        }

        context = build_correlation_context(
            request=request,
            headers=headers,
            resolver_match=resolver_match,
            status_code=201,
            tracing_id=None,
        )

        self.assertEqual(context["request_id"], "req-123")
        self.assertEqual(context["trace_id"], "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(context["status_class"], "2xx")
        self.assertEqual(context["url_name"], "test_api")
        self.assertEqual(context["actor_id"], "actor_123")
        self.assertEqual(context["tenant_id"], "tenant_456")
        self.assertNotIn("username", context)

    def test_low_cardinality_metadata_excludes_high_cardinality_ids(self):
        data = {
            "request_id": "req-1",
            "trace_id": "trace-1",
            "route": "api/test/",
            "view_name": "tests.urls.test_api_view",
            "app_name": "",
            "namespace": "",
            "url_name": "test_api",
            "status_class": "2xx",
            "actor_id": "actor_123",
        }

        labels = build_low_cardinality_metadata(data)

        self.assertEqual(labels["route"], "api/test/")
        self.assertEqual(labels["url_name"], "test_api")
        self.assertEqual(labels["status_class"], "2xx")
        self.assertNotIn("request_id", labels)
        self.assertNotIn("trace_id", labels)
        self.assertNotIn("actor_id", labels)


class LoggingContextTests(TestCase):
    def tearDown(self):
        clear_correlation_context()

    def test_logging_context_is_copy_safe_and_clearable(self):
        context = {
            "request_id": "req-1",
            "trace_id": "trace-1",
            "route": "api/test/",
        }

        set_correlation_context(context)

        self.assertEqual(get_correlation_context(), context)
        get_correlation_context()["request_id"] = "mutated"
        self.assertEqual(get_correlation_context()["request_id"], "req-1")

        clear_correlation_context()
        self.assertEqual(get_correlation_context(), {})
