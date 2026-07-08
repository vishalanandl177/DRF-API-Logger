from django.conf import settings
from django.utils.module_loading import import_string


UNKNOWN_LABEL_VALUE = "unknown"

DEFAULT_METRICS_GROUPS = ("logger", "pipeline")
DEFAULT_METRIC_LABELS = ("method", "route", "view_name", "status_class")

ALLOWED_LABELS = frozenset(
    {
        "method",
        "route",
        "view_name",
        "url_name",
        "app_name",
        "namespace",
        "status_code",
        "status_class",
        "exception_class",
        "auth_scheme",
        "reason",
        "severity",
        "category",
        "rule_id",
        "event_type",
        "attack_type",
        "location",
        "payload",
        "queue_name",
        "worker_name",
        "storage_backend",
        "logging_enabled",
        "outcome",
        "throttle_scope",
        "feature",
        "middleware_name",
        "renderer",
    }
)

FORBIDDEN_LABELS = frozenset(
    {
        "raw_path",
        "full_url",
        "query_string",
        "request_id",
        "trace_id",
        "user_id",
        "email",
        "username",
        "client_ip",
        "authorization_header",
        "token",
        "api_key",
        "session_id",
        "object_id",
        "tenant_id",
        "actor_id",
        "sql_query",
        "exception_message",
        "request_body",
        "response_body",
        "full_user_agent",
    }
)


def _setting(name, default):
    return getattr(settings, name, default)


def _as_bool(name, default=False):
    return bool(_setting(name, default))


def metrics_enabled():
    return _as_bool("DRF_API_LOGGER_METRICS_ENABLED", False)


def metrics_exporter():
    value = _setting("DRF_API_LOGGER_METRICS_EXPORTER", "prometheus")
    if value not in ("none", "prometheus"):
        return "prometheus"
    return value


def metrics_groups():
    value = _setting("DRF_API_LOGGER_METRICS_GROUPS", DEFAULT_METRICS_GROUPS)
    if not isinstance(value, (list, tuple, set)):
        return DEFAULT_METRICS_GROUPS
    normalized = []
    for group in value:
        text = str(group).strip().lower()
        if text in {"api", "logger", "pipeline", "profiling", "security"}:
            normalized.append(text)
    return tuple(normalized) or DEFAULT_METRICS_GROUPS


def metric_label_keys():
    value = _setting("DRF_API_LOGGER_METRICS_LABELS", DEFAULT_METRIC_LABELS)
    if not isinstance(value, (list, tuple)):
        value = DEFAULT_METRIC_LABELS
    return tuple(label for label in value if label in ALLOWED_LABELS)


def unsafe_metric_label_keys():
    value = _setting("DRF_API_LOGGER_METRICS_LABELS", DEFAULT_METRIC_LABELS)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(label for label in value if label not in ALLOWED_LABELS or label in FORBIDDEN_LABELS)


def max_label_length():
    value = _setting("DRF_API_LOGGER_METRICS_MAX_LABEL_LENGTH", 128)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 128


def prometheus_namespace():
    value = str(_setting("DRF_API_LOGGER_METRICS_PROMETHEUS_NAMESPACE", "drf_api_logger")).strip()
    return value or "drf_api_logger"


def prometheus_endpoint_enabled():
    return _as_bool("DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED", False)


def prometheus_endpoint_path():
    value = str(_setting("DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_PATH", "metrics/")).strip()
    if not value:
        return "metrics/"
    return value if value.endswith("/") else value + "/"


def histogram_buckets_seconds():
    value = _setting(
        "DRF_API_LOGGER_METRICS_HISTOGRAM_BUCKETS_SECONDS",
        (
            0.001,
            0.0025,
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2.5,
            5,
            10,
        ),
    )
    if not isinstance(value, (list, tuple)):
        return None
    buckets = []
    for item in value:
        if isinstance(item, (int, float)) and not isinstance(item, bool) and item > 0:
            buckets.append(float(item))
    return tuple(buckets) or None


def histogram_buckets_bytes():
    value = _setting(
        "DRF_API_LOGGER_METRICS_SIZE_BUCKETS_BYTES",
        (
            100,
            500,
            1000,
            5000,
            10000,
            50000,
            100000,
            500000,
            1000000,
            5000000,
        ),
    )
    if not isinstance(value, (list, tuple)):
        return None
    buckets = []
    for item in value:
        if isinstance(item, (int, float)) and not isinstance(item, bool) and item > 0:
            buckets.append(float(item))
    return tuple(buckets) or None


def slow_request_threshold_seconds():
    value = _setting("DRF_API_LOGGER_SLOW_API_ABOVE", None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value / 1000.0
    return None


def api_metrics_enabled():
    return metrics_enabled() and _as_bool("DRF_API_LOGGER_API_METRICS_ENABLED", False)


def logger_metrics_enabled():
    return metrics_enabled() and "logger" in metrics_groups()


def pipeline_metrics_enabled():
    return metrics_enabled() and "pipeline" in metrics_groups()


def profiling_metrics_enabled():
    return metrics_enabled() and "profiling" in metrics_groups()


def security_metrics_enabled():
    return (
        metrics_enabled()
        and _as_bool("DRF_API_LOGGER_SECURITY_METRICS_ENABLED", False)
        and "security" in set(metrics_groups() + ("security",))
    )


def request_metrics_enabled():
    return api_metrics_enabled() or security_metrics_enabled()


def security_mode():
    return "detect"


def security_body_inspection_config():
    default = {
        "enabled": True,
        "max_body_bytes": 8192,
        "inspect_request_body": True,
        "inspect_response_body": False,
    }
    value = _setting("DRF_API_LOGGER_SECURITY_BODY_INSPECTION", default)
    if not isinstance(value, dict):
        value = {}
    config = default.copy()
    config.update(value)
    return config


def security_body_inspection_limit():
    value = security_body_inspection_config().get("max_body_bytes", 8192)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 8192


def inspect_request_body_for_security():
    config = security_body_inspection_config()
    return bool(config.get("enabled", True)) and bool(config.get("inspect_request_body", True))


def inspect_response_body_for_security():
    config = security_body_inspection_config()
    return bool(config.get("enabled", True)) and bool(config.get("inspect_response_body", False))


def security_rules_config():
    value = _setting("DRF_API_LOGGER_SECURITY_RULES", {})
    return value if isinstance(value, dict) else {}


def security_window_seconds():
    value = _setting("DRF_API_LOGGER_SECURITY_WINDOW_SECONDS", 300)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 300


def security_actor_tracking_config():
    default = {
        "enabled": True,
        "strategy": "hmac_fingerprint",
        "include_user_id": True,
        "include_ip": True,
        "include_user_agent_family": True,
    }
    value = _setting("DRF_API_LOGGER_SECURITY_ACTOR_TRACKING", default)
    if not isinstance(value, dict):
        value = {}
    config = default.copy()
    config.update(value)
    return config


def security_context_getter():
    dotted_path = _setting("DRF_API_LOGGER_SECURITY_CONTEXT_GETTER", None)
    if not dotted_path:
        return None
    if callable(dotted_path):
        return dotted_path
    try:
        return import_string(str(dotted_path))
    except Exception:
        return None
