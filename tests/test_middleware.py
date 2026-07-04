"""
Test cases for APILoggerMiddleware
"""
import json
import os
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.test.utils import override_settings

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware


def middleware_exploding_policy(context):
    raise RuntimeError("policy failed with Authorization=Bearer secret-token")


class TestAPILoggerMiddleware(TestCase):
    """Test cases for the API Logger Middleware"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.middleware = APILoggerMiddleware(get_response=self.get_response)
        
    def get_response(self, request):
        """Mock get_response function"""
        response = HttpResponse(
            json.dumps({"message": "test response"}),
            content_type="application/json",
            status=200
        )
        return response

    def test_middleware_initialization(self):
        """Test middleware initializes correctly with default settings"""
        with override_settings(
            DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE=32768,
            DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE=65536,
        ):
            middleware = APILoggerMiddleware(get_response=Mock())
        self.assertIsNotNone(middleware)
        self.assertEqual(middleware.DRF_API_LOGGER_PATH_TYPE, 'ABSOLUTE')
        self.assertEqual(middleware.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE, 32768)
        self.assertEqual(middleware.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE, 65536)

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_sync_logger_disabled_bypasses_logging_setup(self):
        """Test disabled logging still returns the response."""
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/test/')

        response = middleware(request)

        self.assertEqual(response.status_code, 200)

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    def test_middleware_with_database_enabled(self):
        """Test middleware when database logging is enabled"""
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_DATABASE)

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    def test_middleware_with_signal_enabled(self):
        """Test middleware when signal logging is enabled"""
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_SIGNAL)

    def test_static_file_request_skip(self):
        """Test that static file requests are skipped"""
        request = self.factory.get('/static/test.css')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_media_file_request_skip(self):
        """Test that media file requests are skipped"""
        request = self.factory.get('/media/test.jpg')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_admin_namespace_skip(self, mock_resolve):
        """Test that admin namespace requests are skipped"""
        mock_resolve.return_value.namespace = 'admin'
        mock_resolve.return_value.url_name = 'index'
        
        request = self.factory.get('/admin/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SKIP_URL_NAME=['test_view']
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_skip_url_name(self, mock_resolve):
        """Test skipping specific URL names"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test_view'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/test/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SKIP_NAMESPACE=['api_v1']
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_skip_namespace(self, mock_resolve):
        """Test skipping specific namespaces"""
        mock_resolve.return_value.namespace = 'api_v1'
        mock_resolve.return_value.url_name = 'list'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/v1/users/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_METHODS=['GET', 'POST']
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_method_filtering(self, mock_thread, mock_resolve):
        """Test that only specified methods are logged"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        mock_thread.put_log_data = Mock()
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        
        # Test GET request (should be logged)
        request = self.factory.get('/api/test/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        
        # Test DELETE request (should not be logged)
        request = self.factory.delete('/api/test/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_STATUS_CODES=[200, 201]
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_status_code_filtering(self, mock_thread, mock_resolve):
        """Test that only specified status codes are logged"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        mock_thread.put_log_data = Mock()
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/test/')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_ENABLE_TRACING=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_tracing_enabled(self, mock_resolve):
        """Test tracing ID generation when enabled"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/test/')
        response = middleware(request)
        
        self.assertTrue(hasattr(request, 'tracing_id'))
        self.assertIsNotNone(request.tracing_id)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_ENABLE_TRACING=True,
        DRF_API_LOGGER_TRACING_ID_HEADER_NAME='X_TRACE_ID'  # Note: HTTP_ prefix is removed by get_headers
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_tracing_from_header(self, mock_resolve):
        """Test tracing ID from request header"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        request = self.factory.get('/api/test/', HTTP_X_TRACE_ID='test-trace-123')
        response = middleware(request)
        
        self.assertEqual(request.tracing_id, 'test-trace-123')

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE=100
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_max_request_body_size(self, mock_resolve):
        """Test request body size limitation"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        large_body = json.dumps({"data": "x" * 1000})
        request = self.factory.post('/api/test/', 
                                   data=large_body,
                                   content_type='application/json')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE=20
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_request_body_truncation_marker(self, mock_resolve):
        """Test oversized request body is marked as truncated"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            large_body = json.dumps({"data": "x" * 100})
            request = self.factory.post(
                '/api/test/',
                data=large_body,
                content_type='application/json'
            )
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Request body truncated', signal_data[0]['body'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE=20
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_response_body_truncation_marker(self, mock_resolve):
        """Test oversized response body is marked as truncated"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        def large_response(request):
            return HttpResponse(
                json.dumps({"data": "x" * 100}),
                content_type="application/json",
                status=200
            )

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=large_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Response body truncated', signal_data[0]['response'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_json_content_type_with_charset_is_logged(self, mock_resolve):
        """Test JSON responses with charset parameters are logged"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        def charset_response(request):
            return HttpResponse(
                json.dumps({"message": "ok"}),
                content_type="application/json; charset=utf-8",
                status=200
            )

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=charset_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data[0]['response']['message'], 'ok')
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_CONTENT_TYPES=['text/plain']
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_custom_text_content_type_is_logged(self, mock_resolve):
        """Test configured non-JSON content types are logged"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        def text_response(request):
            return HttpResponse("plain response", content_type="text/plain", status=200)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=text_response)
            request = self.factory.post(
                '/api/test/',
                data="plain request",
                content_type='text/plain'
            )
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data[0]['body'], 'plain request')
            self.assertEqual(signal_data[0]['response'], 'plain response')
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SAMPLE_RATE=0
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_profiling_sample_rate_zero_skips_profiling(self, mock_resolve):
        """Test profiling sample rate can disable profiling capture"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('profiling_data', signal_data[0])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SAMPLE_RATE=0.5
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.random.random', return_value=0.1)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_profiling_sample_rate_uses_random_sampling(self, mock_resolve, mock_random):
        """Test fractional profiling sample rates use random sampling."""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertIn('profiling_data', signal_data[0])
            mock_random.assert_called_once()
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_CORRELATION=True,
        DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_correlation_context_on_request_logging_context_and_signal(self, mock_resolve):
        """Test correlation context is exposed outside DB persistence."""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response

        from drf_api_logger import API_LOGGER_SIGNAL
        from drf_api_logger.logging_context import get_correlation_context

        signal_data = []
        captured = {}

        def listener(**kwargs):
            signal_data.append(kwargs)

        def correlated_response(request):
            captured['request_context'] = request.api_logger_correlation.copy()
            captured['logging_context'] = get_correlation_context()
            return self.get_response(request)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=correlated_response)
            request = self.factory.get(
                '/api/test/',
                HTTP_X_REQUEST_ID='req-123',
                HTTP_TRACEPARENT='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            )
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(request.api_logger_request_id, 'req-123')
            self.assertEqual(request.api_logger_trace_id, '4bf92f3577b34da6a3ce929d0e0e4736')
            self.assertEqual(request.tracing_id, '4bf92f3577b34da6a3ce929d0e0e4736')
            self.assertEqual(captured['request_context']['request_id'], 'req-123')
            self.assertEqual(captured['logging_context']['trace_id'], '4bf92f3577b34da6a3ce929d0e0e4736')
            self.assertEqual(get_correlation_context(), {})

            self.assertEqual(signal_data[0]['correlation']['request_id'], 'req-123')
            self.assertEqual(signal_data[0]['correlation']['status_class'], '2xx')
            self.assertEqual(signal_data[0]['low_cardinality']['route'], 'api/test/')
            self.assertEqual(signal_data[0]['low_cardinality']['status_class'], '2xx')
            self.assertNotIn('request_id', signal_data[0]['low_cardinality'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_CORRELATION=True,
        DRF_API_LOGGER_ENABLE_TRACING=False
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_correlation_does_not_generate_trace_ids_when_tracing_is_disabled(self, mock_resolve):
        """Test correlation remains inbound-only when tracing is off."""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response

        from drf_api_logger import API_LOGGER_SIGNAL

        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertFalse(hasattr(request, 'tracing_id'))
            self.assertNotIn('trace_id', signal_data[0]['correlation'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_PATH_TYPE='FULL_PATH'
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_path_type_full_path(self, mock_resolve):
        """Test FULL_PATH path type setting"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        self.assertEqual(middleware.DRF_API_LOGGER_PATH_TYPE, 'FULL_PATH')

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_PATH_TYPE='RAW_URI'
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_path_type_raw_uri(self, mock_resolve):
        """Test RAW_URI path type setting"""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        
        middleware = APILoggerMiddleware(get_response=self.get_response)
        self.assertEqual(middleware.DRF_API_LOGGER_PATH_TYPE, 'RAW_URI')

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_PATH_TYPE='RAW_URI'
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_path_type_raw_uri_logs_with_request_raw_uri(self, mock_resolve):
        """Test RAW_URI uses the sync request raw URI method when available."""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/?token=query-secret')
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertIn('/api/test/?token=***FILTERED***', signal_data[0]['api'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_PATH_TYPE='RAW_URI')
    def test_raw_uri_helper_uses_request_get_raw_uri_when_available(self):
        """Test RAW_URI keeps using request.get_raw_uri for sync requests."""
        middleware = APILoggerMiddleware(get_response=self.get_response)

        class RequestWithRawUri:
            def get_raw_uri(self):
                return 'raw://example.test/api/test/?token=query-secret'

        self.assertEqual(
            middleware._request_api(RequestWithRawUri()),
            'raw://example.test/api/test/?token=query-secret',
        )

    @override_settings(
        DRF_API_LOGGER_DATABASE=False,
        DRF_API_LOGGER_SIGNAL=True,
        USE_TZ=False
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_added_on_uses_naive_datetime_when_use_tz_false(self, mock_resolve):
        """Test USE_TZ=False keeps backward-compatible naive timestamps."""
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(signal_data[0]['added_on'].tzinfo)
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    def test_json_request_body_parsing(self):
        """Test parsing of JSON request body"""
        request = self.factory.post('/api/test/',
                                   data=json.dumps({"key": "value"}),
                                   content_type='application/json')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_body_decoding_defensive_edges(self):
        """Test body decoding handles malformed and inaccessible bodies."""
        middleware = APILoggerMiddleware(get_response=self.get_response)

        class RequestWithUnreadableBody:
            META = {'CONTENT_TYPE': 'application/json'}

            @property
            def body(self):
                raise RuntimeError('body unavailable')

        class ResponseWithUnreadableContent:
            streaming = False

            def get(self, key):
                return 'application/json'

            @property
            def content(self):
                raise RuntimeError('content unavailable')

        self.assertEqual(
            middleware._decode_body('plain request', -1, 'Request body', 'text/plain'),
            'plain request',
        )
        self.assertEqual(
            middleware._decode_body(b'\xff', -1, 'Request body', 'application/json'),
            '',
        )
        self.assertEqual(
            middleware._decode_body(b'not-json', -1, 'Request body', 'application/json'),
            '',
        )
        self.assertEqual(
            middleware._decode_body(b'not-json', -1, 'Request body', 'application/octet-stream'),
            '',
        )
        self.assertEqual(middleware._get_request_data(RequestWithUnreadableBody()), '')
        self.assertEqual(middleware._get_response_body(ResponseWithUnreadableContent()), '')

    def test_non_json_request_body(self):
        """Test handling of non-JSON request body"""
        request = self.factory.post('/api/test/',
                                   data="plain text data",
                                   content_type='text/plain')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_exception_in_url_resolution(self, mock_resolve):
        """Test handling of exceptions in URL resolution"""
        mock_resolve.side_effect = Exception("Resolution failed")
        
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_POLICY={
            "rules": [
                {"url_name": "test", "log": False, "reason": "skip_test_endpoint"},
            ]
        }
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_policy_can_skip_database_and_signal_logging(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response
        mock_thread.put_log_data = Mock()

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.get('/api/test/')
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            mock_thread.put_log_data.assert_not_called()
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_POLICY={
            "rules": [
                {
                    "url_name": "test",
                    "headers": False,
                    "request_body": False,
                    "response_body": False,
                    "signal": False,
                    "reason": "metadata_only",
                },
            ]
        }
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_policy_can_strip_payloads_and_disable_signal_only(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response
        mock_thread.put_log_data = Mock()

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.post(
                '/api/test/',
                data=json.dumps({"email": "developer@example.invalid"}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer secret-token',
            )
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            mock_thread.put_log_data.assert_called_once()
            call_data = mock_thread.put_log_data.call_args[1]['data']
            self.assertEqual(call_data['headers'], '')
            self.assertEqual(call_data['body'], '')
            self.assertEqual(call_data['response'], '')
            self.assertEqual(signal_data, [])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_POLICY={
            "rules": [
                {
                    "url_name": "test",
                    "mask_keys": ["email"],
                    "reason": "mask_endpoint_email",
                },
            ]
        }
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_policy_extra_mask_keys_apply_before_signal_export(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.post(
                '/api/test/?email=developer@example.invalid',
                data=json.dumps({"email": "developer@example.invalid"}),
                content_type='application/json',
            )
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(signal_data[0]['body']['email'], '***FILTERED***')
            self.assertIn('email=***FILTERED***', signal_data[0]['api'])
            self.assertEqual(signal_data[0]['policy']['reason'], 'mask_endpoint_email')
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_POLICY_FUNC="tests.test_middleware.middleware_exploding_policy"
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_policy_failure_logs_safe_metadata_only(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.app_name = None
        mock_resolve.return_value.url_name = 'test'
        mock_resolve.return_value.route = 'api/test/'
        mock_resolve.return_value.func = self.get_response
        mock_thread.put_log_data = Mock()

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []

        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_response)
            request = self.factory.post(
                '/api/test/?email=developer@example.invalid',
                data=json.dumps({"password": "secret", "email": "developer@example.invalid"}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer secret-token',
            )
            response = middleware(request)

            self.assertEqual(response.status_code, 200)
            mock_thread.put_log_data.assert_called_once()
            call_data = mock_thread.put_log_data.call_args[1]['data']
            self.assertEqual(call_data['headers'], '')
            self.assertEqual(call_data['body'], '')
            self.assertEqual(call_data['response'], '')
            self.assertEqual(signal_data, [])
            self.assertNotIn('secret-token', str(call_data))
            self.assertNotIn('developer@example.invalid', str(call_data))
            self.assertNotIn('email=', str(call_data))
        finally:
            API_LOGGER_SIGNAL.listen -= listener
