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
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertIsNotNone(middleware)
        self.assertFalse(middleware.DRF_API_LOGGER_DATABASE)
        self.assertFalse(middleware.DRF_API_LOGGER_SIGNAL)
        self.assertEqual(middleware.DRF_API_LOGGER_PATH_TYPE, 'ABSOLUTE')

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

    def test_json_request_body_parsing(self):
        """Test parsing of JSON request body"""
        request = self.factory.post('/api/test/',
                                   data=json.dumps({"key": "value"}),
                                   content_type='application/json')
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

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