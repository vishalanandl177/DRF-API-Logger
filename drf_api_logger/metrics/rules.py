import re

from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.security import SecuritySignal
from drf_api_logger.metrics.state import BoundedRollingState


PAYLOAD_ATTACK_RE = re.compile(
    rb"(<script\b|javascript:|union\s+select|\bor\b\s+1\s*=\s*1|--|/\*|\.\./|%2e%2e)",
    re.IGNORECASE,
)
LOG_INJECTION_RE = re.compile(rb"(\r\n|\n|\r)")
OBJECT_ID_PATH_RE = re.compile(r"/\d+(?:/|$)")


def _new_state():
    return BoundedRollingState(max_keys=1000, ttl_seconds=metrics_settings.security_window_seconds())


AUTH_FAILURE_STATE = _new_state()
OBJECT_ENUMERATION_STATE = _new_state()
PAGINATION_SWEEP_STATE = _new_state()
BUSINESS_FLOW_STATE = _new_state()


def reset_security_rule_state_for_tests():
    global AUTH_FAILURE_STATE, OBJECT_ENUMERATION_STATE, PAGINATION_SWEEP_STATE, BUSINESS_FLOW_STATE
    AUTH_FAILURE_STATE = _new_state()
    OBJECT_ENUMERATION_STATE = _new_state()
    PAGINATION_SWEEP_STATE = _new_state()
    BUSINESS_FLOW_STATE = _new_state()


def _body_sample(context):
    sample = context.request_body_sample
    if sample is None:
        return b""
    if isinstance(sample, bytes):
        return sample
    try:
        return str(sample).encode("utf-8", errors="ignore")
    except Exception:
        return b""


def _response_sample(context):
    sample = context.response_body_sample
    if sample is None:
        return b""
    if isinstance(sample, bytes):
        return sample
    try:
        return str(sample).encode("utf-8", errors="ignore")
    except Exception:
        return b""


def _signal(context, rule_id, event_type, category, severity, score, reason="unknown"):
    return SecuritySignal(
        rule_id=rule_id,
        event_type=event_type,
        category=category,
        severity=severity,
        score=score,
        route=context.route or "unknown",
        method=context.method or "unknown",
        status_class=context.status_class or "unknown",
        outcome="observed",
        reason=reason,
    )


def _actor_key(context, suffix):
    actor = context.actor_fingerprint or "anonymous"
    route = context.route or "unknown"
    return "{}:{}:{}".format(suffix, actor, route)


def _request_path(context):
    request = getattr(context, "request", None)
    path = getattr(request, "path", "")
    return str(path or "")


def _query_value(context, key):
    request = getattr(context, "request", None)
    query = getattr(request, "GET", None)
    if not query:
        return None
    try:
        if hasattr(query, "get"):
            return query.get(key)
        return query[key]
    except Exception:
        return None


class SecurityRule:
    rule_id = "DRFSEC-000"
    category = "unknown"

    def evaluate(self, context):
        return []


class AuthFailureRule(SecurityRule):
    rule_id = "DRFSEC-001"
    category = "authentication"

    def evaluate(self, context):
        if context.status_code == 401:
            AUTH_FAILURE_STATE.increment(_actor_key(context, "auth_failure"))
            return [_signal(context, self.rule_id, "auth_failure", self.category, "warning", 3, "auth_failure")]
        return []


class SuccessAfterFailuresRule(SecurityRule):
    rule_id = "DRFSEC-002"
    category = "authentication"

    def evaluate(self, context):
        if context.status_code is None or context.status_code < 200 or context.status_code > 299:
            return []
        count = AUTH_FAILURE_STATE.get(_actor_key(context, "auth_failure"))
        if count >= 3:
            return [
                _signal(
                    context,
                    self.rule_id,
                    "success_after_auth_failures",
                    self.category,
                    "warning",
                    4,
                    "success_after_failures",
                )
            ]
        return []


class TokenFailureRule(SecurityRule):
    rule_id = "DRFSEC-003"
    category = "token"

    def evaluate(self, context):
        route = str(context.route or "").lower()
        if context.status_code == 401 and ("token" in route or "auth" in route):
            return [_signal(context, self.rule_id, "token_failure_burst", self.category, "warning", 3, "token_failure")]
        return []


class AuthorizationFailureRule(SecurityRule):
    rule_id = "DRFSEC-004"
    category = "authorization"

    def evaluate(self, context):
        if context.status_code == 403:
            return [
                _signal(
                    context,
                    self.rule_id,
                    "authorization_failure",
                    self.category,
                    "warning",
                    3,
                    "authorization_failure",
                )
            ]
        return []


class AdminProbeRule(SecurityRule):
    rule_id = "DRFSEC-005"
    category = "reconnaissance"

    def evaluate(self, context):
        route = str(context.route or "").lower()
        if "admin" in route or "debug" in route:
            return [_signal(context, self.rule_id, "admin_probe", self.category, "warning", 3, "admin_probe")]
        return []


class PayloadAttackPatternRule(SecurityRule):
    rule_id = "DRFSEC-006"
    category = "payload"

    def evaluate(self, context):
        sample = _body_sample(context)
        if sample and PAYLOAD_ATTACK_RE.search(sample):
            return [
                _signal(
                    context,
                    self.rule_id,
                    "payload_attack_pattern",
                    self.category,
                    "warning",
                    4,
                    "payload_pattern",
                )
            ]
        return []


class RateLimitPressureRule(SecurityRule):
    rule_id = "DRFSEC-007"
    category = "resource_abuse"

    def evaluate(self, context):
        if context.status_code == 429:
            return [_signal(context, self.rule_id, "rate_limit_pressure", self.category, "warning", 3, "rate_limited")]
        return []


class RouteScanRule(SecurityRule):
    rule_id = "DRFSEC-008"
    category = "reconnaissance"

    def evaluate(self, context):
        if context.status_code == 404:
            return [_signal(context, self.rule_id, "route_scan_suspected", self.category, "notice", 2, "not_found")]
        return []


class ObjectIdEnumerationRule(SecurityRule):
    rule_id = "DRFSEC-009"
    category = "authorization"

    def evaluate(self, context):
        if context.status_code not in (403, 404):
            return []
        path = _request_path(context)
        route = str(context.route or "")
        if not (OBJECT_ID_PATH_RE.search(path) or "<int:" in route or "<uuid:" in route):
            return []
        count = OBJECT_ENUMERATION_STATE.increment(_actor_key(context, "object_id"))
        if count >= 3:
            return [
                _signal(
                    context,
                    self.rule_id,
                    "object_id_enumeration_suspected",
                    self.category,
                    "warning",
                    4,
                    "object_probe",
                )
            ]
        return []


class LogInjectionRule(SecurityRule):
    rule_id = "DRFSEC-010"
    category = "payload"

    def evaluate(self, context):
        sample = _body_sample(context)
        if sample and LOG_INJECTION_RE.search(sample):
            return [_signal(context, self.rule_id, "log_injection_attempt", self.category, "notice", 2, "control_chars")]
        return []


class SensitiveFieldExposureRule(SecurityRule):
    rule_id = "DRFSEC-011"
    category = "data_exposure"

    def evaluate(self, context):
        sample = _response_sample(context).lower()
        if b"password" in sample or b"api_key" in sample or b"authorization" in sample:
            return [
                _signal(
                    context,
                    self.rule_id,
                    "sensitive_field_exposure_suspected",
                    self.category,
                    "warning",
                    4,
                    "sensitive_field",
                )
            ]
        return []


class PaginationSweepRule(SecurityRule):
    rule_id = "DRFSEC-012"
    category = "scraping"

    def evaluate(self, context):
        page = _query_value(context, "page")
        cursor = _query_value(context, "cursor")
        if page is None and cursor is None:
            return []
        count = PAGINATION_SWEEP_STATE.increment(_actor_key(context, "pagination"))
        if count >= 3:
            return [_signal(context, self.rule_id, "pagination_sweep_suspected", self.category, "notice", 2)]
        return []


class BulkExportSpikeRule(SecurityRule):
    rule_id = "DRFSEC-013"
    category = "data_exfiltration"

    def evaluate(self, context):
        route = str(context.route or "").lower()
        action = str(context.business_context.get("business_action", "")).lower()
        if any(marker in route for marker in ("export", "download", "report")) or "export" in action:
            return [_signal(context, self.rule_id, "bulk_export_suspected", self.category, "warning", 4)]
        return []


class HighResponseVolumeRule(SecurityRule):
    rule_id = "DRFSEC-014"
    category = "data_exfiltration"

    def evaluate(self, context):
        sample = _response_sample(context)
        if len(sample) >= 8192:
            return [_signal(context, self.rule_id, "high_response_volume_suspected", self.category, "notice", 2)]
        return []


class SensitiveBusinessRouteRule(SecurityRule):
    rule_id = "DRFSEC-015"
    category = "business_logic"

    def evaluate(self, context):
        if context.business_context.get("is_sensitive_route") is True:
            return [_signal(context, self.rule_id, "sensitive_route_access", self.category, "notice", 2)]
        return []


class BusinessFlowAbuseRule(SecurityRule):
    rule_id = "DRFSEC-016"
    category = "business_logic"

    def evaluate(self, context):
        flow = context.business_context.get("flow_name")
        action = context.business_context.get("business_action")
        if not flow or not action:
            return []
        key = "{}:{}:{}:{}".format(
            "business_flow",
            context.actor_fingerprint or "anonymous",
            flow,
            action,
        )
        count = BUSINESS_FLOW_STATE.increment(key)
        if count >= 3:
            return [_signal(context, self.rule_id, "business_flow_abuse_suspected", self.category, "warning", 4)]
        return []


RULES = (
    ("auth_abuse", AuthFailureRule()),
    ("auth_abuse", SuccessAfterFailuresRule()),
    ("token_abuse", TokenFailureRule()),
    ("auth_abuse", AuthorizationFailureRule()),
    ("admin_probe", AdminProbeRule()),
    ("payload_attack_patterns", PayloadAttackPatternRule()),
    ("resource_abuse", RateLimitPressureRule()),
    ("route_scan", RouteScanRule()),
    ("object_id_enumeration", ObjectIdEnumerationRule()),
    ("payload_attack_patterns", LogInjectionRule()),
    ("payload_attack_patterns", SensitiveFieldExposureRule()),
    ("data_exfiltration", PaginationSweepRule()),
    ("data_exfiltration", BulkExportSpikeRule()),
    ("data_exfiltration", HighResponseVolumeRule()),
    ("business_logic_hooks", SensitiveBusinessRouteRule()),
    ("business_logic_hooks", BusinessFlowAbuseRule()),
)


def iter_security_rules(enabled_rules):
    for setting_key, rule in RULES:
        if enabled_rules.get(setting_key, False):
            yield rule
