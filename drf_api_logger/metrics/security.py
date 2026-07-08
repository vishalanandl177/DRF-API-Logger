from dataclasses import dataclass

from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.labels import _safe_enum_value


@dataclass(frozen=True)
class SecuritySignal:
    rule_id: str
    event_type: str
    category: str
    severity: str
    score: int
    route: str
    method: str
    status_class: str
    outcome: str = "observed"
    reason: str = "unknown"


@dataclass
class SecurityContext:
    request: object
    response: object | None
    exception: Exception | None
    route: str
    method: str
    status_code: int | None
    status_class: str
    request_body_sample: str | bytes | None
    response_body_sample: str | bytes | None
    actor_fingerprint: str | None
    low_cardinality: dict
    business_context: dict


def enabled_rules():
    configured = metrics_settings.security_rules_config()
    return {
        "auth_abuse": configured.get("auth_abuse", True),
        "token_abuse": configured.get("token_abuse", True),
        "route_scan": configured.get("route_scan", True),
        "admin_probe": configured.get("admin_probe", True),
        "object_id_enumeration": configured.get("object_id_enumeration", True),
        "payload_attack_patterns": configured.get("payload_attack_patterns", True),
        "resource_abuse": configured.get("resource_abuse", True),
        "data_exfiltration": configured.get("data_exfiltration", True),
        "business_logic_hooks": configured.get("business_logic_hooks", False),
    }


def sanitize_business_context(value):
    if not isinstance(value, dict):
        return {}
    safe = {}
    for key in ("actor_type", "business_action", "resource_type", "flow_name"):
        if key in value:
            safe[key] = _safe_enum_value(value.get(key))
    if "is_sensitive_route" in value:
        safe["is_sensitive_route"] = value.get("is_sensitive_route") is True
    return safe


def evaluate_security_signals(context, error_callback=None):
    from drf_api_logger.metrics.rules import iter_security_rules

    signals = []
    rules = enabled_rules()
    for rule in iter_security_rules(rules):
        try:
            signals.extend(rule.evaluate(context))
        except Exception as exc:
            if error_callback is not None:
                error_callback(getattr(rule, "rule_id", "unknown"), exc)
    return signals
