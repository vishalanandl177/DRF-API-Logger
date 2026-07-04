import re


CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
UNKNOWN_LABEL_VALUE = "unknown"

DEFAULT_METRIC_LABELS = (
    "route",
    "url_name",
    "app_name",
    "namespace",
    "status_class",
    "method",
)

LOW_CARDINALITY_CONTEXT_KEYS = (
    "route",
    "view_name",
    "app_name",
    "namespace",
    "url_name",
    "status_class",
)

CORRELATION_ID_KEYS = (
    "request_id",
    "trace_id",
)

OPAQUE_CONTEXT_KEYS = (
    "actor_id",
    "tenant_id",
    "api_consumer_id",
    "client_id",
)


def _safe_text(value, max_length=256):
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None
    if len(value) > max_length:
        return None
    if CONTROL_CHAR_RE.search(value):
        return None
    return value


def _safe_label_value(value):
    return _safe_text(value, max_length=256) or UNKNOWN_LABEL_VALUE


def _event_dict(event, key):
    value = event.get(key, {})
    if type(value) is dict:
        return value
    return {}


def build_metric_labels(event, label_keys=DEFAULT_METRIC_LABELS):
    low_cardinality = _event_dict(event, "low_cardinality")
    labels = {}

    for key in label_keys:
        if key == "method":
            value = event.get("method")
        else:
            value = low_cardinality.get(key)
        labels[key] = _safe_label_value(value)

    return labels


def _execution_time_seconds(event):
    try:
        value = float(event.get("execution_time"))
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _status_code(event):
    try:
        value = int(event.get("status_code"))
    except (TypeError, ValueError):
        return None
    if value < 100 or value > 599:
        return None
    return value


def record_prometheus_metrics(event, request_counter, duration_observer=None):
    labels = build_metric_labels(event)
    request_counter.labels(**labels).inc()

    duration_seconds = _execution_time_seconds(event)
    if duration_observer is not None and duration_seconds is not None:
        duration_observer.labels(**labels).observe(duration_seconds)

    return labels


def build_span_attributes(event, include_high_cardinality=False):
    low_cardinality = _event_dict(event, "low_cardinality")
    correlation = _event_dict(event, "correlation")
    attrs = {}

    method = _safe_text(event.get("method"))
    if method:
        attrs["http.request.method"] = method

    status_code = _status_code(event)
    if status_code is not None:
        attrs["http.response.status_code"] = status_code

    duration_seconds = _execution_time_seconds(event)
    if duration_seconds is not None:
        attrs["drf_api_logger.execution_time_ms"] = round(duration_seconds * 1000, 5)

    for key in LOW_CARDINALITY_CONTEXT_KEYS:
        value = _safe_text(low_cardinality.get(key))
        if value:
            attrs["drf_api_logger.{}".format(key)] = value

    if include_high_cardinality:
        for key in CORRELATION_ID_KEYS:
            value = _safe_text(correlation.get(key))
            if value:
                attrs["drf_api_logger.{}".format(key)] = value

    return attrs


def annotate_opentelemetry_span(span, event, include_high_cardinality=False):
    attrs = build_span_attributes(
        event,
        include_high_cardinality=include_high_cardinality,
    )

    if span is None:
        return attrs

    for key, value in attrs.items():
        span.set_attribute(key, value)

    return attrs


def build_sentry_context(event, include_high_cardinality=True):
    low_cardinality = _event_dict(event, "low_cardinality")
    correlation = _event_dict(event, "correlation")
    context = {}

    method = _safe_text(event.get("method"))
    if method:
        context["method"] = method

    status_code = _status_code(event)
    if status_code is not None:
        context["status_code"] = status_code

    duration_seconds = _execution_time_seconds(event)
    if duration_seconds is not None:
        context["execution_time_ms"] = round(duration_seconds * 1000, 5)

    for key in LOW_CARDINALITY_CONTEXT_KEYS:
        value = _safe_text(low_cardinality.get(key))
        if value:
            context[key] = value

    if include_high_cardinality:
        for key in CORRELATION_ID_KEYS + OPAQUE_CONTEXT_KEYS:
            value = _safe_text(correlation.get(key))
            if value:
                context[key] = value

    return context


def configure_sentry_scope(scope, event, include_high_cardinality=True):
    tag_labels = build_metric_labels(
        event,
        label_keys=("route", "url_name", "status_class", "method"),
    )
    context = build_sentry_context(
        event,
        include_high_cardinality=include_high_cardinality,
    )

    if scope is not None:
        for key, value in tag_labels.items():
            if value != UNKNOWN_LABEL_VALUE:
                scope.set_tag("drf_api_logger.{}".format(key), value)
        if context:
            scope.set_context("drf_api_logger", context)

    return {
        "tags": tag_labels,
        "context": context,
    }
