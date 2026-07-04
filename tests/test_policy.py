from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import resolve
from unittest.mock import Mock

from drf_api_logger.policy import (
    LoggingPolicyDecision,
    build_policy_context,
    decision_from_mapping,
    evaluate_logging_policy,
    safe_evaluate_logging_policy,
)


def callable_policy(context):
    if context["url_name"] == "test_api":
        return {
            "request_body": False,
            "response_body": False,
            "mask_keys": ["email"],
            "reason": "callable_test_api_policy",
        }
    return {"log": True}


def exploding_policy(context):
    raise RuntimeError("secret policy failure with token=abc123")


class LoggingPolicyDecisionTests(TestCase):
    def test_default_decision_is_backward_compatible(self):
        decision = LoggingPolicyDecision()

        self.assertTrue(decision.log)
        self.assertTrue(decision.database)
        self.assertTrue(decision.signal)
        self.assertTrue(decision.headers)
        self.assertTrue(decision.request_body)
        self.assertTrue(decision.response_body)
        self.assertEqual(decision.mask_keys, ())
        self.assertEqual(decision.reason, "default")
        self.assertFalse(decision.policy_error)

    def test_decision_from_mapping_normalizes_booleans_and_mask_keys(self):
        decision = decision_from_mapping(
            {
                "log": False,
                "database": False,
                "signal": False,
                "headers": False,
                "request_body": False,
                "response_body": False,
                "mask_keys": ["email", "account_id", ""],
                "reason": "drop_sensitive_endpoint",
            }
        )

        self.assertFalse(decision.log)
        self.assertFalse(decision.database)
        self.assertFalse(decision.signal)
        self.assertFalse(decision.headers)
        self.assertFalse(decision.request_body)
        self.assertFalse(decision.response_body)
        self.assertEqual(decision.mask_keys, ("email", "account_id"))
        self.assertEqual(decision.reason, "drop_sensitive_endpoint")


class LoggingPolicyEvaluationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post(
            "/api/test/",
            data='{"email": "developer@example.invalid"}',
            content_type="application/json",
        )
        self.request.resolver_match = resolve("/api/test/")

    def test_build_policy_context_uses_request_response_and_resolver_metadata(self):
        response = type("Response", (), {"status_code": 201})()
        context = build_policy_context(
            request=self.request,
            response=response,
            resolver_match=self.request.resolver_match,
            correlation_context={"status_class": "2xx"},
            low_cardinality={"route": "api/test/", "url_name": "test_api"},
        )

        self.assertEqual(context["path"], "/api/test/")
        self.assertEqual(context["method"], "POST")
        self.assertEqual(context["status_code"], 201)
        self.assertEqual(context["status_class"], "2xx")
        self.assertEqual(context["route"], "api/test/")
        self.assertEqual(context["url_name"], "test_api")

    def test_build_policy_context_ignores_mock_view_metadata(self):
        resolver_match = Mock()
        resolver_match.route = "api/test/"
        resolver_match.url_name = "test_api"
        resolver_match.namespace = None
        resolver_match.app_name = None

        context = build_policy_context(
            request=self.request,
            response=type("Response", (), {"status_code": 200})(),
            resolver_match=resolver_match,
        )

        self.assertEqual(context["route"], "api/test/")
        self.assertEqual(context["url_name"], "test_api")
        self.assertIsNone(context["view_name"])

    @override_settings(
        DRF_API_LOGGER_POLICY={
            "rules": [
                {"url_name": "test_api", "log": False, "reason": "skip_test_api"},
            ]
        }
    )
    def test_rule_can_skip_all_logging_for_matching_url_name(self):
        decision = evaluate_logging_policy(
            request=self.request,
            response=type("Response", (), {"status_code": 200})(),
            resolver_match=self.request.resolver_match,
            correlation_context={"status_class": "2xx"},
            low_cardinality={"route": "api/test/", "url_name": "test_api"},
        )

        self.assertFalse(decision.log)
        self.assertFalse(decision.database)
        self.assertFalse(decision.signal)
        self.assertEqual(decision.reason, "skip_test_api")

    @override_settings(
        DRF_API_LOGGER_POLICY={
            "rules": [
                {
                    "route": "api/test/",
                    "methods": ["POST"],
                    "status_classes": ["2xx"],
                    "request_body": False,
                    "response_body": False,
                    "headers": False,
                    "signal": False,
                    "mask_keys": ["email"],
                    "reason": "metadata_only_success",
                },
            ]
        }
    )
    def test_rule_can_strip_payloads_mask_extra_keys_and_disable_signal(self):
        decision = evaluate_logging_policy(
            request=self.request,
            response=type("Response", (), {"status_code": 200})(),
            resolver_match=self.request.resolver_match,
            correlation_context={"status_class": "2xx"},
            low_cardinality={"route": "api/test/", "url_name": "test_api"},
        )

        self.assertTrue(decision.log)
        self.assertTrue(decision.database)
        self.assertFalse(decision.signal)
        self.assertFalse(decision.headers)
        self.assertFalse(decision.request_body)
        self.assertFalse(decision.response_body)
        self.assertEqual(decision.mask_keys, ("email",))
        self.assertEqual(decision.reason, "metadata_only_success")

    @override_settings(DRF_API_LOGGER_POLICY_FUNC="tests.test_policy.callable_policy")
    def test_callable_policy_can_override_decision(self):
        decision = evaluate_logging_policy(
            request=self.request,
            response=type("Response", (), {"status_code": 200})(),
            resolver_match=self.request.resolver_match,
            correlation_context={"status_class": "2xx"},
            low_cardinality={"route": "api/test/", "url_name": "test_api"},
        )

        self.assertTrue(decision.log)
        self.assertFalse(decision.request_body)
        self.assertFalse(decision.response_body)
        self.assertEqual(decision.mask_keys, ("email",))
        self.assertEqual(decision.reason, "callable_test_api_policy")

    @override_settings(DRF_API_LOGGER_POLICY_FUNC="tests.test_policy.exploding_policy")
    def test_safe_evaluation_fails_closed_without_leaking_exception_text(self):
        decision = safe_evaluate_logging_policy(
            request=self.request,
            response=type("Response", (), {"status_code": 200})(),
            resolver_match=self.request.resolver_match,
            correlation_context={"status_class": "2xx"},
            low_cardinality={"route": "api/test/", "url_name": "test_api"},
        )

        self.assertTrue(decision.log)
        self.assertTrue(decision.database)
        self.assertFalse(decision.signal)
        self.assertFalse(decision.headers)
        self.assertFalse(decision.request_body)
        self.assertFalse(decision.response_body)
        self.assertTrue(decision.policy_error)
        self.assertEqual(decision.reason, "policy_error_metadata_only")
        self.assertNotIn("token", decision.to_signal_metadata().get("reason", ""))
