from django.test import TestCase

from drf_api_logger.observability import (
    annotate_opentelemetry_span,
    build_metric_labels,
    build_sentry_context,
    build_span_attributes,
    configure_sentry_scope,
    record_prometheus_metrics,
)


class FakeCounter:
    def __init__(self):
        self.calls = []
        self._labels = None

    def labels(self, **labels):
        self._labels = labels
        return self

    def inc(self):
        self.calls.append(("inc", self._labels.copy()))


class FakeObserver:
    def __init__(self):
        self.calls = []
        self._labels = None

    def labels(self, **labels):
        self._labels = labels
        return self

    def observe(self, value):
        self.calls.append(("observe", self._labels.copy(), value))


class FakeSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeScope:
    def __init__(self):
        self.tags = {}
        self.contexts = {}

    def set_tag(self, key, value):
        self.tags[key] = value

    def set_context(self, key, value):
        self.contexts[key] = value


class ObservabilityHelperTests(TestCase):
    def event(self):
        return {
            "method": "GET",
            "status_code": 200,
            "execution_time": 0.125,
            "headers": {"AUTHORIZATION": "***FILTERED***"},
            "body": {"password": "***FILTERED***"},
            "response": {"ok": True},
            "correlation": {
                "request_id": "req-123",
                "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                "actor_id": "actor_123",
                "tenant_id": "tenant_456",
                "client_id": "client_abc",
            },
            "low_cardinality": {
                "route": "api/test/",
                "url_name": "test_api",
                "app_name": "tests",
                "namespace": "public",
                "status_class": "2xx",
            },
        }

    def test_metric_labels_use_only_low_cardinality_values(self):
        labels = build_metric_labels(self.event())

        self.assertEqual(
            labels,
            {
                "route": "api/test/",
                "url_name": "test_api",
                "app_name": "tests",
                "namespace": "public",
                "status_class": "2xx",
                "method": "GET",
            },
        )
        self.assertNotIn("request_id", labels)
        self.assertNotIn("trace_id", labels)
        self.assertNotIn("actor_id", labels)
        self.assertNotIn("tenant_id", labels)

    def test_metric_labels_fill_missing_values_with_unknown(self):
        event = {"method": "POST", "low_cardinality": {"status_class": "5xx"}}

        labels = build_metric_labels(event)

        self.assertEqual(labels["method"], "POST")
        self.assertEqual(labels["status_class"], "5xx")
        self.assertEqual(labels["route"], "unknown")
        self.assertEqual(labels["url_name"], "unknown")

    def test_metric_labels_treat_blank_and_malformed_context_as_unknown(self):
        event = {"method": "   ", "low_cardinality": ["not", "a", "dict"]}

        labels = build_metric_labels(event)

        self.assertEqual(labels["method"], "unknown")
        self.assertEqual(labels["route"], "unknown")
        self.assertEqual(labels["url_name"], "unknown")

    def test_metric_labels_reject_control_characters_and_long_values(self):
        event = {
            "method": "GET\nunsafe",
            "low_cardinality": {
                "route": "api/test/",
                "url_name": "x" * 257,
                "status_class": "2xx",
            },
        }

        labels = build_metric_labels(event)

        self.assertEqual(labels["method"], "unknown")
        self.assertEqual(labels["route"], "api/test/")
        self.assertEqual(labels["url_name"], "unknown")
        self.assertEqual(labels["status_class"], "2xx")

    def test_record_prometheus_metrics_updates_counter_and_observer(self):
        counter = FakeCounter()
        observer = FakeObserver()

        labels = record_prometheus_metrics(self.event(), counter, observer)

        self.assertEqual(counter.calls, [("inc", labels)])
        self.assertEqual(observer.calls, [("observe", labels, 0.125)])

    def test_record_prometheus_metrics_skips_invalid_duration_values(self):
        counter = FakeCounter()
        observer = FakeObserver()

        record_prometheus_metrics({"method": "GET", "execution_time": "slow"}, counter, observer)
        record_prometheus_metrics({"method": "GET", "execution_time": -1}, counter, observer)

        self.assertEqual(len(counter.calls), 2)
        self.assertEqual(observer.calls, [])

    def test_span_attributes_are_low_cardinality_by_default(self):
        attrs = build_span_attributes(self.event())

        self.assertEqual(attrs["http.request.method"], "GET")
        self.assertEqual(attrs["http.response.status_code"], 200)
        self.assertEqual(attrs["drf_api_logger.execution_time_ms"], 125.0)
        self.assertEqual(attrs["drf_api_logger.route"], "api/test/")
        self.assertEqual(attrs["drf_api_logger.status_class"], "2xx")
        self.assertNotIn("drf_api_logger.request_id", attrs)
        self.assertNotIn("drf_api_logger.trace_id", attrs)

    def test_span_attributes_can_include_correlation_ids_explicitly(self):
        attrs = build_span_attributes(self.event(), include_high_cardinality=True)

        self.assertEqual(attrs["drf_api_logger.request_id"], "req-123")
        self.assertEqual(attrs["drf_api_logger.trace_id"], "4bf92f3577b34da6a3ce929d0e0e4736")

    def test_span_attributes_skip_invalid_status_codes_and_durations(self):
        attrs = build_span_attributes(
            {"method": "GET", "status_code": "bad", "execution_time": "slow"}
        )
        out_of_range_attrs = build_span_attributes(
            {"method": "GET", "status_code": 99, "execution_time": -1}
        )

        self.assertNotIn("http.response.status_code", attrs)
        self.assertNotIn("drf_api_logger.execution_time_ms", attrs)
        self.assertNotIn("http.response.status_code", out_of_range_attrs)
        self.assertNotIn("drf_api_logger.execution_time_ms", out_of_range_attrs)

    def test_annotate_opentelemetry_span_sets_attributes(self):
        span = FakeSpan()

        attrs = annotate_opentelemetry_span(span, self.event())

        self.assertEqual(span.attributes, attrs)
        self.assertEqual(span.attributes["drf_api_logger.route"], "api/test/")

    def test_annotate_opentelemetry_span_allows_missing_current_span(self):
        attrs = annotate_opentelemetry_span(None, self.event())

        self.assertEqual(attrs["drf_api_logger.route"], "api/test/")

    def test_sentry_context_excludes_payloads_and_headers(self):
        context = build_sentry_context(self.event())

        self.assertEqual(context["request_id"], "req-123")
        self.assertEqual(context["trace_id"], "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(context["route"], "api/test/")
        self.assertEqual(context["method"], "GET")
        self.assertEqual(context["status_code"], 200)
        self.assertNotIn("headers", context)
        self.assertNotIn("body", context)
        self.assertNotIn("response", context)

    def test_configure_sentry_scope_sets_low_cardinality_tags_and_context(self):
        scope = FakeScope()

        result = configure_sentry_scope(scope, self.event())

        self.assertEqual(scope.tags["drf_api_logger.route"], "api/test/")
        self.assertEqual(scope.tags["drf_api_logger.status_class"], "2xx")
        self.assertNotIn("drf_api_logger.request_id", scope.tags)
        self.assertEqual(scope.contexts["drf_api_logger"], result["context"])
        self.assertEqual(scope.contexts["drf_api_logger"]["request_id"], "req-123")
