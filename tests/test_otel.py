"""
Test cases for OpenTelemetry integration.
Tests work with mocked OTel SDK to avoid requiring the actual dependency.
"""
import json
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.test.utils import override_settings

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware
from drf_api_logger.utils import otel_enabled


class TestOtelEnabled(TestCase):

    @override_settings(DRF_API_LOGGER_ENABLE_OTEL=False)
    def test_otel_disabled(self):
        self.assertFalse(otel_enabled())

    @override_settings(DRF_API_LOGGER_ENABLE_OTEL=True)
    def test_otel_enabled(self):
        self.assertTrue(otel_enabled())

    def test_otel_not_set(self):
        self.assertFalse(otel_enabled())


class TestMiddlewareOtelInit(TestCase):

    def test_otel_defaults_false(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertFalse(middleware.DRF_API_LOGGER_ENABLE_OTEL)

    @override_settings(DRF_API_LOGGER_ENABLE_OTEL=True)
    def test_otel_enabled_from_settings(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_ENABLE_OTEL)


class TestOtelModule(TestCase):
    """Test the otel.py module with mocked opentelemetry."""

    def test_has_otel_false_when_not_installed(self):
        with patch.dict('sys.modules', {'opentelemetry': None, 'opentelemetry.trace': None}):
            import importlib
            import drf_api_logger.otel as otel_mod
            importlib.reload(otel_mod)
            self.assertFalse(otel_mod.HAS_OTEL)
            span, owned = otel_mod.start_span('GET', '/api/test/')
            self.assertIsNone(span)
            self.assertIsNone(owned)
            otel_mod.finish_span(None, False, {})

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.trace')
    def test_start_span_creates_own_when_no_current(self, mock_trace):
        from drf_api_logger.otel import start_span, get_tracer
        import drf_api_logger.otel as otel_mod
        otel_mod._tracer = None

        mock_tracer = Mock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_current = Mock()
        mock_current.is_recording.return_value = False
        mock_trace.get_current_span.return_value = mock_current

        mock_new_span = Mock()
        mock_tracer.start_span.return_value = mock_new_span

        span, owned = start_span('GET', '/api/test/')
        self.assertEqual(span, mock_new_span)
        self.assertTrue(owned)

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.trace')
    def test_start_span_reuses_existing(self, mock_trace):
        from drf_api_logger.otel import start_span
        import drf_api_logger.otel as otel_mod
        otel_mod._tracer = Mock()

        mock_current = Mock()
        mock_current.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_current

        span, owned = start_span('POST', '/api/users/')
        self.assertEqual(span, mock_current)
        self.assertFalse(owned)

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    def test_finish_span_sets_attributes(self):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {
            'method': 'GET',
            'api': '/api/test/',
            'status_code': 200,
            'client_ip_address': '127.0.0.1',
            'execution_time': 0.150,
        }
        finish_span(mock_span, False, data)

        mock_span.set_attribute.assert_any_call('http.method', 'GET')
        mock_span.set_attribute.assert_any_call('http.url', '/api/test/')
        mock_span.set_attribute.assert_any_call('http.status_code', 200)
        mock_span.set_attribute.assert_any_call('http.client_ip', '127.0.0.1')
        mock_span.set_attribute.assert_any_call('drf.execution_time_ms', 150.0)
        mock_span.end.assert_not_called()

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    def test_finish_span_ends_owned_span(self):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 200,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, True, data)
        mock_span.end.assert_called_once()

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    def test_finish_span_does_not_end_borrowed_span(self):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 200,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, False, data)
        mock_span.end.assert_not_called()

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.StatusCode')
    def test_finish_span_sets_error_for_5xx(self, mock_status_code):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 500,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, True, data)
        mock_span.set_status.assert_called_once_with(mock_status_code.ERROR, 'HTTP 500')

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.StatusCode')
    def test_finish_span_sets_error_for_4xx(self, mock_status_code):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 404,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, True, data)
        mock_span.set_status.assert_called_once_with(mock_status_code.ERROR, 'HTTP 404')

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.StatusCode')
    def test_finish_span_sets_ok_for_2xx(self, mock_status_code):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 200,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, True, data)
        mock_span.set_status.assert_called_once_with(mock_status_code.OK)

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    def test_finish_span_with_profiling_data(self):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 200,
                'client_ip_address': '', 'execution_time': 1.0}
        profiling = {
            'middleware_before_view': 0.001,
            'view_and_serialization': 0.995,
            'middleware_after_view': 0.002,
            'sql': {'total_time': 0.8, 'query_count': 47},
        }
        finish_span(mock_span, True, data, profiling)

        mock_span.set_attribute.assert_any_call('drf.profiling.middleware_before_view_ms', 1.0)
        mock_span.set_attribute.assert_any_call('drf.profiling.view_and_serialization_ms', 995.0)
        mock_span.set_attribute.assert_any_call('drf.profiling.middleware_after_view_ms', 2.0)
        mock_span.set_attribute.assert_any_call('db.query_count', 47)
        mock_span.set_attribute.assert_any_call('db.total_time_ms', 800.0)

    @patch('drf_api_logger.otel.HAS_OTEL', True)
    def test_finish_span_without_profiling(self):
        from drf_api_logger.otel import finish_span

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        data = {'method': 'GET', 'api': '/', 'status_code': 200,
                'client_ip_address': '', 'execution_time': 0.01}
        finish_span(mock_span, True, data, profiling=None)

        calls = [str(c) for c in mock_span.set_attribute.call_args_list]
        for c in calls:
            self.assertNotIn('db.query_count', c)
            self.assertNotIn('drf.profiling', c)

    def test_finish_span_noop_when_no_otel(self):
        from drf_api_logger.otel import finish_span
        finish_span(None, False, {})


class TestMiddlewareOtelIntegration(TestCase):
    """Test OTel integration in the middleware end-to-end."""

    def setUp(self):
        self.factory = RequestFactory()

    def get_json_response(self, request):
        return HttpResponse(
            json.dumps({"ok": True}),
            content_type="application/json",
            status=200
        )

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_OTEL=True,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.trace')
    def test_otel_span_created_and_finished(self, mock_trace, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        import drf_api_logger.otel as otel_mod
        otel_mod._tracer = None

        mock_tracer = Mock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_current = Mock()
        mock_current.is_recording.return_value = False
        mock_trace.get_current_span.return_value = mock_current

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_tracer.start_span.return_value = mock_span

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)
        API_LOGGER_SIGNAL.listen += listener

        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            mock_tracer.start_span.assert_called_once()
            mock_span.set_attribute.assert_any_call('http.method', 'GET')
            mock_span.set_attribute.assert_any_call('http.status_code', 200)
            mock_span.end.assert_called_once()
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_OTEL=False,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_no_otel_when_disabled(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)
        API_LOGGER_SIGNAL.listen += listener

        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)

            with patch('drf_api_logger.otel.start_span') as mock_start:
                request = self.factory.get('/api/test/')
                middleware(request)
                mock_start.assert_not_called()
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_OTEL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=True,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.otel.HAS_OTEL', True)
    @patch('drf_api_logger.otel.trace')
    def test_otel_span_includes_profiling(self, mock_trace, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        import drf_api_logger.otel as otel_mod
        otel_mod._tracer = None

        mock_tracer = Mock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_current = Mock()
        mock_current.is_recording.return_value = False
        mock_trace.get_current_span.return_value = mock_current

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_tracer.start_span.return_value = mock_span

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)
        API_LOGGER_SIGNAL.listen += listener

        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            attr_calls = {str(c) for c in mock_span.set_attribute.call_args_list}
            attr_names = [c[0][0] for c in mock_span.set_attribute.call_args_list]
            self.assertIn('drf.profiling.view_and_serialization_ms', attr_names)
            self.assertIn('db.query_count', attr_names)
        finally:
            API_LOGGER_SIGNAL.listen -= listener
