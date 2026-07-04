from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


MATCH_RULE_KEYS = {
    "route": ("route", "routes"),
    "url_name": ("url_name", "url_names"),
    "namespace": ("namespace", "namespaces"),
    "app_name": ("app_name", "app_names"),
    "view_name": ("view_name", "view_names"),
    "method": ("method", "methods"),
    "status_code": ("status_code", "status_codes"),
    "status_class": ("status_class", "status_classes"),
}


@dataclass(frozen=True)
class LoggingPolicyDecision:
    log: bool = True
    database: bool = True
    signal: bool = True
    headers: bool = True
    request_body: bool = True
    response_body: bool = True
    mask_keys: tuple = ()
    reason: str = "default"
    policy_error: bool = False

    def __post_init__(self):
        if not self.log:
            object.__setattr__(self, "database", False)
            object.__setattr__(self, "signal", False)

    def to_signal_metadata(self):
        metadata = {
            "log": self.log,
            "database": self.database,
            "signal": self.signal,
            "headers": self.headers,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "reason": self.reason,
        }
        if self.mask_keys:
            metadata["mask_keys"] = list(self.mask_keys)
        if self.policy_error:
            metadata["policy_error"] = True
        return metadata


def _as_bool(value, default):
    if type(value) is bool:
        return value
    return default


def _as_mask_keys(value):
    if type(value) not in (list, tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def decision_from_mapping(mapping, base=None):
    if not mapping:
        return base or LoggingPolicyDecision()

    if base is None:
        base = LoggingPolicyDecision()

    log = _as_bool(mapping.get("log"), base.log)
    database = _as_bool(mapping.get("database"), base.database)
    signal = _as_bool(mapping.get("signal"), base.signal)
    headers = _as_bool(mapping.get("headers"), base.headers)
    request_body = _as_bool(mapping.get("request_body"), base.request_body)
    response_body = _as_bool(mapping.get("response_body"), base.response_body)
    mask_keys = base.mask_keys + _as_mask_keys(mapping.get("mask_keys"))
    reason = str(mapping.get("reason") or base.reason)
    policy_error = _as_bool(mapping.get("policy_error"), base.policy_error)

    return LoggingPolicyDecision(
        log=log,
        database=database,
        signal=signal,
        headers=headers,
        request_body=request_body,
        response_body=response_body,
        mask_keys=mask_keys,
        reason=reason,
        policy_error=policy_error,
    )


def _resolver_value(resolver_match, name):
    if resolver_match is None:
        return None
    return getattr(resolver_match, name, None)


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


def _status_class(status_code):
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        return None
    if status_code < 100 or status_code > 599:
        return None
    return "{}xx".format(status_code // 100)


def build_policy_context(
    request,
    response=None,
    resolver_match=None,
    correlation_context=None,
    low_cardinality=None,
):
    correlation_context = correlation_context or {}
    low_cardinality = low_cardinality or {}
    status_code = getattr(response, "status_code", None)
    status_bucket = (
        correlation_context.get("status_class")
        or low_cardinality.get("status_class")
        or _status_class(status_code)
    )

    return {
        "path": getattr(request, "path", None),
        "path_info": getattr(request, "path_info", None),
        "method": getattr(request, "method", None),
        "status_code": status_code,
        "status_class": status_bucket,
        "route": low_cardinality.get("route") or _resolver_value(resolver_match, "route"),
        "url_name": low_cardinality.get("url_name") or _resolver_value(resolver_match, "url_name"),
        "namespace": low_cardinality.get("namespace") or _resolver_value(resolver_match, "namespace"),
        "app_name": low_cardinality.get("app_name") or _resolver_value(resolver_match, "app_name"),
        "view_name": low_cardinality.get("view_name") or _view_name(resolver_match),
        "correlation": correlation_context.copy(),
        "low_cardinality": low_cardinality.copy(),
    }


def _matches_value(expected, actual):
    if type(expected) in (list, tuple, set):
        return actual in expected
    return actual == expected


def _rule_matches(rule, context):
    for context_key, rule_keys in MATCH_RULE_KEYS.items():
        for rule_key in rule_keys:
            if rule_key in rule and not _matches_value(rule[rule_key], context.get(context_key)):
                return False

    path_prefix = rule.get("path_prefix")
    if path_prefix and not str(context.get("path") or "").startswith(str(path_prefix)):
        return False

    return True


def _policy_config():
    value = getattr(settings, "DRF_API_LOGGER_POLICY", None)
    if type(value) is dict:
        return value
    return {}


def _apply_declarative_policy(context):
    config = _policy_config()
    decision = decision_from_mapping(config.get("default"))

    rules = config.get("rules", [])
    if type(rules) not in (list, tuple):
        return decision

    for rule in rules:
        if type(rule) is dict and _rule_matches(rule, context):
            decision = decision_from_mapping(rule, base=decision)
    return decision


def _apply_callable_policy(context, decision):
    policy_func = getattr(settings, "DRF_API_LOGGER_POLICY_FUNC", None)
    if not policy_func:
        return decision

    result = import_string(policy_func)(context)
    if isinstance(result, LoggingPolicyDecision):
        return result
    if type(result) is dict:
        return decision_from_mapping(result, base=decision)
    return decision


def evaluate_logging_policy(
    request,
    response=None,
    resolver_match=None,
    correlation_context=None,
    low_cardinality=None,
):
    context = build_policy_context(
        request=request,
        response=response,
        resolver_match=resolver_match,
        correlation_context=correlation_context,
        low_cardinality=low_cardinality,
    )
    decision = _apply_declarative_policy(context)
    return _apply_callable_policy(context, decision)


def safe_evaluate_logging_policy(
    request,
    response=None,
    resolver_match=None,
    correlation_context=None,
    low_cardinality=None,
):
    try:
        return evaluate_logging_policy(
            request=request,
            response=response,
            resolver_match=resolver_match,
            correlation_context=correlation_context,
            low_cardinality=low_cardinality,
        )
    except Exception:
        return LoggingPolicyDecision(
            log=True,
            database=True,
            signal=False,
            headers=False,
            request_body=False,
            response_body=False,
            reason="policy_error_metadata_only",
            policy_error=True,
        )
