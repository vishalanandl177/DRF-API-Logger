import re

from drf_api_logger.metrics import settings as metrics_settings


CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
SAFE_ENUM_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
UNRESOLVED_ROUTE_LABEL = "unresolved"
UNRESOLVED_VIEW_LABEL = "unresolved"


def _safe_text(value, max_length=None):
    if value is None:
        return None
    max_length = max_length or metrics_settings.max_label_length()
    value = str(value).strip()
    if not value or len(value) > max_length:
        return None
    if CONTROL_CHAR_RE.search(value):
        return None
    return value


def _safe_label_value(value):
    return _safe_text(value) or metrics_settings.UNKNOWN_LABEL_VALUE


def _safe_enum_value(value):
    value = _safe_text(value, max_length=64)
    if not value or not SAFE_ENUM_RE.match(value):
        return metrics_settings.UNKNOWN_LABEL_VALUE
    return value


def _safe_method(value):
    value = _safe_text(value, max_length=16)
    if not value:
        return metrics_settings.UNKNOWN_LABEL_VALUE
    value = value.upper()
    if not SAFE_ENUM_RE.match(value):
        return metrics_settings.UNKNOWN_LABEL_VALUE
    return value


def status_class(status_code):
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        return metrics_settings.UNKNOWN_LABEL_VALUE
    if status_code < 100 or status_code > 599:
        return metrics_settings.UNKNOWN_LABEL_VALUE
    return "{}xx".format(status_code // 100)


def _view_name(resolver_match):
    if resolver_match is None:
        return None
    view_func = getattr(resolver_match, "func", None)
    view_class = getattr(view_func, "view_class", None)
    class_module = getattr(view_class, "__module__", None)
    class_name = getattr(view_class, "__name__", None)
    if type(class_module) is str and type(class_name) is str:
        return "{}.{}".format(class_module, class_name)

    func_module = getattr(view_func, "__module__", None)
    func_name = getattr(view_func, "__name__", None)
    if type(func_module) is str and type(func_name) is str:
        return "{}.{}".format(func_module, func_name)
    return None


def build_low_cardinality_from_resolver(resolver_match, status_code=None):
    if resolver_match is None:
        return {
            "route": UNRESOLVED_ROUTE_LABEL,
            "view_name": UNRESOLVED_VIEW_LABEL,
            "status_class": status_class(status_code),
        }
    values = {
        "route": getattr(resolver_match, "route", None),
        "view_name": _view_name(resolver_match),
        "app_name": getattr(resolver_match, "app_name", None),
        "namespace": getattr(resolver_match, "namespace", None),
        "url_name": getattr(resolver_match, "url_name", None),
        "status_class": status_class(status_code),
    }
    return {
        key: _safe_label_value(value)
        for key, value in values.items()
        if _safe_text(value) or key == "status_class"
    }


def _event_low_cardinality(event):
    value = event.get("low_cardinality", {})
    return value if type(value) is dict else {}


def build_http_labels(event):
    low_cardinality = _event_low_cardinality(event)
    labels = {}
    for key in metrics_settings.metric_label_keys():
        if key == "method":
            labels[key] = _safe_method(event.get("method"))
        elif key == "status_code":
            labels[key] = _safe_label_value(event.get("status_code"))
        elif key == "status_class":
            labels[key] = _safe_label_value(
                low_cardinality.get("status_class")
                or event.get("status_class")
                or status_class(event.get("status_code"))
            )
        elif key == "route":
            labels[key] = _safe_label_value(low_cardinality.get("route") or event.get("route"))
        elif key in metrics_settings.ALLOWED_LABELS:
            labels[key] = _safe_label_value(low_cardinality.get(key) or event.get(key))
    return labels


def build_http_core_labels(event):
    low_cardinality = _event_low_cardinality(event)
    return {
        "method": _safe_method(event.get("method")),
        "route": _safe_label_value(low_cardinality.get("route") or event.get("route")),
        "view_name": _safe_label_value(low_cardinality.get("view_name") or event.get("view_name")),
        "status_code": _safe_label_value(event.get("status_code")),
        "status_class": _safe_label_value(
            low_cardinality.get("status_class")
            or event.get("status_class")
            or status_class(event.get("status_code"))
        ),
        "exception_class": _safe_enum_value(event.get("exception_class")),
        "throttle_scope": _safe_enum_value(event.get("throttle_scope")),
    }


def build_logger_labels(labels=None):
    labels = labels or {}
    safe = {}
    for key, value in labels.items():
        if key in metrics_settings.ALLOWED_LABELS and key not in metrics_settings.FORBIDDEN_LABELS:
            safe[key] = _safe_label_value(value)
    return safe


def build_security_labels(signal):
    return {
        "event_type": _safe_enum_value(signal.event_type),
        "category": _safe_enum_value(signal.category),
        "severity": _safe_enum_value(signal.severity),
        "rule_id": _safe_enum_value(signal.rule_id),
        "route": _safe_label_value(signal.route),
        "method": _safe_method(signal.method),
        "status_class": _safe_enum_value(signal.status_class),
        "outcome": _safe_enum_value(signal.outcome),
        "reason": _safe_enum_value(signal.reason),
    }
