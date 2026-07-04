import asyncio
import json
from unittest.mock import Mock, patch

from asgiref.sync import iscoroutinefunction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.test import AsyncClient, AsyncRequestFactory, SimpleTestCase
from django.test.utils import override_settings

from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
from drf_api_logger.logging_context import (
    clear_correlation_context,
    get_correlation_context,
)
from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware


def async_test_trace_id():
    return "trace-from-async-test-func"


class AsyncAPILoggerMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = AsyncRequestFactory()

    def tearDown(self):
        clear_correlation_context()

    async def async_response(self, request):
        return JsonResponse({"ok": True})

    def test_middleware_declares_sync_and_async_capability(self):
        middleware = APILoggerMiddleware(get_response=self.async_response)

        self.assertTrue(APILoggerMiddleware.sync_capable)
        self.assertTrue(APILoggerMiddleware.async_capable)
        self.assertTrue(iscoroutinefunction(middleware))

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    async def test_async_signal_logging_captures_masked_payload(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def async_response(request):
            return JsonResponse({
                "ok": True,
                "password": "response-secret",
            })

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=async_response)
            request = self.factory.post(
                "/api/test/?token=query-secret",
                data=json.dumps({
                    "password": "request-secret",
                    "safe": "visible",
                }),
                content_type="application/json",
            )

            response = await middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(signal_data), 1)
            event = signal_data[0]
            self.assertEqual(event["method"], "POST")
            self.assertIn("token=***FILTERED***", event["api"])
            self.assertEqual(event["body"]["password"], "***FILTERED***")
            self.assertEqual(event["body"]["safe"], "visible")
            self.assertEqual(event["response"]["password"], "***FILTERED***")
            self.assertNotIn("query-secret", str(event))
            self.assertNotIn("request-secret", str(event))
            self.assertNotIn("response-secret", str(event))
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    async def test_async_database_logging_enqueues_masked_payload(self):
        async def async_response(request):
            return JsonResponse({"ok": True})

        with patch("drf_api_logger.apps.LOGGER_THREAD") as mock_thread:
            mock_thread.put_log_data = Mock()
            middleware = APILoggerMiddleware(get_response=async_response)
            request = self.factory.post(
                "/api/test/",
                data=json.dumps({
                    "password": "request-secret",
                    "safe": "visible",
                }),
                content_type="application/json",
            )

            response = await middleware(request)

            self.assertEqual(response.status_code, 200)
            mock_thread.put_log_data.assert_called_once()
            event = mock_thread.put_log_data.call_args[1]["data"]
            self.assertEqual(event["method"], "POST")
            self.assertIn('"password": "***FILTERED***"', event["body"])
            self.assertIn('"safe": "visible"', event["body"])
            self.assertNotIn("request-secret", str(event))

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    async def test_async_database_logging_failure_does_not_break_response(self):
        async def async_response(request):
            return JsonResponse({"ok": True})

        with patch("drf_api_logger.apps.LOGGER_THREAD") as mock_thread:
            mock_thread.put_log_data.side_effect = RuntimeError(
                "database unavailable with Authorization=Bearer secret-token"
            )
            middleware = APILoggerMiddleware(get_response=async_response)
            request = self.factory.get("/api/test/")

            response = await middleware(request)

            self.assertEqual(response.status_code, 200)

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    async def test_async_logger_disabled_awaits_response_without_logging_setup(self):
        called = []

        async def async_response(request):
            called.append(True)
            return JsonResponse({"ok": True})

        middleware = APILoggerMiddleware(get_response=async_response)
        response = await middleware(self.factory.get("/api/test/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(called, [True])

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_SKIP_URL_NAME=["skip_me"],
    )
    async def test_async_skip_url_name_awaits_response_without_emitting_signal(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def async_response(request):
            return JsonResponse({"ok": True})

        API_LOGGER_SIGNAL.listen += listener
        try:
            with patch("drf_api_logger.middleware.api_logger_middleware.resolve") as mock_resolve:
                mock_resolve.return_value.namespace = None
                mock_resolve.return_value.url_name = "skip_me"
                middleware = APILoggerMiddleware(get_response=async_response)
                response = await middleware(self.factory.get("/api/test/"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        STATIC_URL="/static/",
        MEDIA_URL="/media/",
    )
    async def test_async_static_request_awaits_response_without_emitting_signal(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            response = await middleware(self.factory.get("/static/test.css"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_STATUS_CODES=[201],
    )
    async def test_async_status_code_filter_skips_signal(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            response = await middleware(self.factory.get("/api/test/"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_METHODS=["POST"],
    )
    async def test_async_method_filter_skips_signal(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            response = await middleware(self.factory.get("/api/test/"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    async def test_async_unsupported_response_content_type_skips_signal(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def html_response(request):
            return HttpResponse("<p>ok</p>", content_type="text/html", status=200)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=html_response)
            response = await middleware(self.factory.get("/api/test/"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_PATH_TYPE="FULL_PATH",
    )
    async def test_async_full_path_setting_controls_logged_api(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            response = await middleware(self.factory.get("/api/test/?token=query-secret"))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data[0]["api"], "/api/test/?token=***FILTERED***")
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_PATH_TYPE="RAW_URI",
    )
    async def test_async_raw_uri_setting_controls_logged_api(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            response = await middleware(self.factory.get("/api/test/?token=query-secret"))

            self.assertEqual(response.status_code, 200)
            self.assertIn("/api/test/?token=***FILTERED***", signal_data[0]["api"])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_TRACING=True,
        DRF_API_LOGGER_TRACING_FUNC="tests.test_asgi_middleware.async_test_trace_id",
    )
    async def test_async_tracing_function_sets_request_and_signal_trace_id(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.async_response)
            request = self.factory.get("/api/test/")
            response = await middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(request.tracing_id, "trace-from-async-test-func")
            self.assertEqual(signal_data[0]["tracing_id"], "trace-from-async-test-func")
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_CONTENT_TYPES=["text/plain"],
    )
    async def test_async_text_content_type_and_json_charset_are_logged(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def text_response(request):
            return HttpResponse("plain response", content_type="text/plain", status=200)

        async def json_charset_response(request):
            return HttpResponse(
                json.dumps({"message": "ok"}),
                content_type="application/json; charset=utf-8",
                status=200,
            )

        API_LOGGER_SIGNAL.listen += listener
        try:
            text_middleware = APILoggerMiddleware(get_response=text_response)
            text_request = self.factory.post(
                "/api/test/",
                data="plain request",
                content_type="text/plain",
            )
            text_result = await text_middleware(text_request)

            json_middleware = APILoggerMiddleware(get_response=json_charset_response)
            json_request = self.factory.get("/api/test/")
            json_result = await json_middleware(json_request)

            self.assertEqual(text_result.status_code, 200)
            self.assertEqual(json_result.status_code, 200)
            self.assertEqual(signal_data[0]["body"], "plain request")
            self.assertEqual(signal_data[0]["response"], "plain response")
            self.assertEqual(signal_data[1]["response"], {"message": "ok"})
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    async def test_async_special_response_markers_match_sync_path(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def streaming_response(request):
            return StreamingHttpResponse(
                iter([b'{"ok": true}']),
                content_type="application/json",
                status=200,
            )

        async def gzip_response(request):
            return HttpResponse(b"gzip-bytes", content_type="application/gzip", status=200)

        async def binary_response(request):
            return HttpResponse(
                b"binary-bytes",
                content_type="application/octet-stream",
                status=200,
            )

        async def calendar_response(request):
            return HttpResponse(
                b"BEGIN:VCALENDAR",
                content_type="text/calendar",
                status=200,
            )

        API_LOGGER_SIGNAL.listen += listener
        try:
            for response_func in (
                streaming_response,
                gzip_response,
                binary_response,
                calendar_response,
            ):
                middleware = APILoggerMiddleware(get_response=response_func)
                response = await middleware(self.factory.get("/api/test/"))
                self.assertEqual(response.status_code, 200)

            self.assertEqual(
                [event["response"] for event in signal_data],
                [
                    "** Streaming **",
                    "** GZIP Archive **",
                    "** Binary File **",
                    "** Calendar **",
                ],
            )
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE=20,
        DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE=20,
    )
    async def test_async_request_and_response_truncation_markers_match_sync_path(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def large_response(request):
            return JsonResponse({"data": "x" * 100})

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=large_response)
            request = self.factory.post(
                "/api/test/",
                data=json.dumps({"data": "x" * 100}),
                content_type="application/json",
            )

            response = await middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertIn("Request body truncated", signal_data[0]["body"])
            self.assertIn("Response body truncated", signal_data[0]["response"])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    async def test_async_database_logging_custom_handler_drop_updates_worker_stats(self):
        async def async_response(request):
            return JsonResponse({"ok": True})

        worker = InsertLogIntoDatabase()
        worker.custom_handler = lambda data: None

        with patch("drf_api_logger.apps.LOGGER_THREAD", worker):
            middleware = APILoggerMiddleware(get_response=async_response)
            response = await middleware(self.factory.get("/api/test/"))

        self.assertEqual(response.status_code, 200)
        status = worker.get_status()
        self.assertEqual(status["dropped_count"], 1)
        self.assertEqual(status["queue_backlog"], 0)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SIGNAL=False,
        DRF_LOGGER_QUEUE_MAX_SIZE=1,
    )
    async def test_async_database_logging_wakes_worker_at_batch_threshold(self):
        async def async_response(request):
            return JsonResponse({"ok": True})

        worker = InsertLogIntoDatabase()

        with patch("drf_api_logger.apps.LOGGER_THREAD", worker):
            middleware = APILoggerMiddleware(get_response=async_response)
            response = await middleware(self.factory.get("/api/test/"))

        self.assertEqual(response.status_code, 200)
        status = worker.get_status()
        self.assertEqual(status["queue_backlog"], 1)
        self.assertTrue(worker._flush_event.is_set())

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_CORRELATION=True,
        DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT=True,
    )
    async def test_concurrent_async_requests_keep_correlation_context_isolated(self):
        captured = {}
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        async def async_response(request):
            request_id = request.api_logger_request_id
            before_yield = get_correlation_context()
            await asyncio.sleep(0)
            after_yield = get_correlation_context()
            captured[request_id] = {
                "request": request.api_logger_correlation.copy(),
                "before_yield": before_yield,
                "after_yield": after_yield,
            }
            return JsonResponse({"request_id": request_id})

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=async_response)
            request_one = self.factory.get(
                "/api/test/",
                headers={
                    "x-request-id": "req-one",
                    "x-trace-id": "trace-one",
                },
            )
            request_two = self.factory.get(
                "/api/test/",
                headers={
                    "x-request-id": "req-two",
                    "x-trace-id": "trace-two",
                },
            )

            responses = await asyncio.gather(
                middleware(request_one),
                middleware(request_two),
            )

            self.assertEqual([response.status_code for response in responses], [200, 200])
            self.assertEqual(captured["req-one"]["request"]["trace_id"], "trace-one")
            self.assertEqual(captured["req-two"]["request"]["trace_id"], "trace-two")
            self.assertEqual(captured["req-one"]["before_yield"]["request_id"], "req-one")
            self.assertEqual(captured["req-two"]["before_yield"]["request_id"], "req-two")
            self.assertEqual(captured["req-one"]["after_yield"]["trace_id"], "trace-one")
            self.assertEqual(captured["req-two"]["after_yield"]["trace_id"], "trace-two")
            self.assertEqual(get_correlation_context(), {})

            signal_by_request_id = {
                event["correlation"]["request_id"]: event
                for event in signal_data
            }
            self.assertEqual(signal_by_request_id["req-one"]["correlation"]["trace_id"], "trace-one")
            self.assertEqual(signal_by_request_id["req-two"]["correlation"]["trace_id"], "trace-two")
            self.assertNotIn("request_id", signal_by_request_id["req-one"]["low_cardinality"])
            self.assertNotIn("trace_id", signal_by_request_id["req-two"]["low_cardinality"])
        finally:
            API_LOGGER_SIGNAL.listen -= listener


class AsyncAPILoggerClientIntegrationTests(SimpleTestCase):
    def tearDown(self):
        clear_correlation_context()

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    async def test_async_client_exercises_middleware_signal_path(self):
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            response = await AsyncClient().post(
                "/api/test/",
                data=json.dumps({"password": "request-secret", "safe": "visible"}),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(signal_data), 1)
            self.assertEqual(signal_data[0]["method"], "POST")
            self.assertEqual(signal_data[0]["body"]["password"], "***FILTERED***")
            self.assertEqual(signal_data[0]["body"]["safe"], "visible")
            self.assertNotIn("request-secret", str(signal_data[0]))
        finally:
            API_LOGGER_SIGNAL.listen -= listener
