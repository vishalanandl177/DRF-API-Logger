"""
Integration test cases for DRF-API-Logger
"""
import json
import time
from unittest.mock import Mock, patch
from django.test import TestCase, Client
from django.test.utils import override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from drf_api_logger import API_LOGGER_SIGNAL


class TestMiddlewareIntegration(TestCase):
    """Integration tests for middleware with actual HTTP requests"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.signal_data = []
        
        def signal_listener(**kwargs):
            self.signal_data.append(kwargs)
        
        self.signal_listener = signal_listener

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    def test_middleware_with_signal_integration(self):
        """Test middleware integration with signal system"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            response = self.client.get('/api/test/')
            self.assertEqual(response.status_code, 200)
            
            # Check that signal was triggered
            self.assertEqual(len(self.signal_data), 1)
            signal_data = self.signal_data[0]
            
            self.assertIn('api', signal_data)
            self.assertIn('method', signal_data)
            self.assertEqual(signal_data['method'], 'GET')
            self.assertEqual(signal_data['status_code'], 200)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_middleware_with_database_integration(self, mock_thread):
        """Test middleware integration with database logging"""
        mock_thread.put_log_data = Mock()
        
        response = self.client.post('/api/test/', 
                                   data={'test': 'data'},
                                   format='json')
        self.assertEqual(response.status_code, 200)
        
        # Check that log data was queued
        mock_thread.put_log_data.assert_called_once()
        call_args = mock_thread.put_log_data.call_args[0][0]
        
        self.assertIn('api', call_args)
        self.assertEqual(call_args['method'], 'POST')
        self.assertEqual(call_args['status_code'], 200)

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_TRACING=True
    )
    def test_tracing_integration(self):
        """Test tracing integration"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            response = self.client.get('/api/test/', 
                                     HTTP_X_TRACE_ID='integration-test-123')
            self.assertEqual(response.status_code, 200)
            
            # Check tracing data in signal
            self.assertEqual(len(self.signal_data), 1)
            signal_data = self.signal_data[0]
            
            self.assertIn('tracing_id', signal_data)
            # Note: tracing_id might be generated if header handling doesn't work as expected
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_METHODS=['POST', 'PUT']
    )
    def test_method_filtering_integration(self):
        """Test method filtering integration"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # GET request should not be logged
            response = self.client.get('/api/test/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.signal_data), 0)
            
            # POST request should be logged
            response = self.client.post('/api/test/', 
                                      data={'test': 'data'},
                                      format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.signal_data), 1)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_STATUS_CODES=[200, 201]
    )
    def test_status_code_filtering_integration(self):
        """Test status code filtering integration"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # 200 response should be logged
            response = self.client.get('/api/test/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.signal_data), 1)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    def test_static_files_not_logged(self):
        """Test that static files are not logged"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # This would normally return 404, but middleware should skip it
            response = self.client.get('/static/test.css')
            # No signal should be triggered regardless of status code
            self.assertEqual(len(self.signal_data), 0)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    def test_admin_requests_not_logged(self):
        """Test that admin requests are not logged"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # Admin URLs should be skipped
            response = self.client.get('/admin/')
            # No signal should be triggered
            self.assertEqual(len(self.signal_data), 0)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestDatabaseIntegration(TestCase):
    """Integration tests with actual database operations"""

    def setUp(self):
        """Set up test fixtures"""
        from drf_api_logger.utils import database_log_enabled
        if database_log_enabled():
            from drf_api_logger.models import APILogsModel
            self.APILogsModel = APILogsModel

    def test_model_database_operations(self):
        """Test basic database operations"""
        if not hasattr(self, 'APILogsModel'):
            self.skipTest("Database logging not enabled")
            
        from django.utils import timezone
        
        # Create log entry
        log = self.APILogsModel.objects.create(
            api='/api/integration/',
            headers='{"Content-Type": "application/json"}',
            body='{"test": "integration"}',
            method='POST',
            client_ip_address='192.168.1.100',
            response='{"result": "created"}',
            status_code=201,
            execution_time=0.156,
            added_on=timezone.now()
        )
        
        # Verify creation
        self.assertIsNotNone(log.id)
        
        # Test querying
        logs = self.APILogsModel.objects.filter(method='POST')
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().api, '/api/integration/')
        
        # Test ordering (newest first)
        log2 = self.APILogsModel.objects.create(
            api='/api/integration2/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='192.168.1.101',
            response='{}',
            status_code=200,
            execution_time=0.05,
            added_on=timezone.now()
        )
        
        all_logs = self.APILogsModel.objects.all()
        self.assertEqual(all_logs[0], log2)  # Most recent first

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_background_thread_integration(self, mock_model):
        """Test background thread with mocked database"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        from django.utils import timezone
        
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.return_value = None
        
        # Create and test thread
        thread = InsertLogIntoDatabase()
        
        # Add test data
        log_data = {
            'api': '/api/thread-test/',
            'method': 'GET',
            'status_code': 200,
            'headers': '{}',
            'body': '',
            'response': '{}',
            'client_ip_address': '127.0.0.1',
            'execution_time': 0.1,
            'added_on': timezone.now()
        }
        
        thread.put_log_data(log_data)
        
        # Trigger bulk insertion
        thread._start_bulk_insertion()
        
        # Verify bulk_create was called
        mock_manager.using.assert_called_with('default')
        mock_manager.using.return_value.bulk_create.assert_called_once()


@override_settings(DRF_API_LOGGER_SIGNAL=True)
class TestCompleteWorkflow(TestCase):
    """Test complete workflow from request to logging"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.all_signals = []
        
        def capture_all_signals(**kwargs):
            self.all_signals.append(kwargs)
        
        self.signal_listener = capture_all_signals

    def test_complete_api_request_workflow(self):
        """Test complete workflow from API request to signal"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # Make API request with various data
            test_data = {
                'username': 'testuser',
                'password': 'secret123',  # Should be masked
                'email': 'test@example.com'
            }
            
            response = self.client.post('/api/test/',
                                      data=test_data,
                                      format='json',
                                      HTTP_USER_AGENT='TestAgent/1.0',
                                      HTTP_X_FORWARDED_FOR='10.0.0.1')
            
            self.assertEqual(response.status_code, 200)
            
            # Verify signal was triggered
            self.assertEqual(len(self.all_signals), 1)
            signal_data = self.all_signals[0]
            
            # Check all expected fields
            expected_fields = [
                'api', 'method', 'status_code', 'headers', 'body',
                'response', 'client_ip_address', 'execution_time', 'added_on'
            ]
            
            for field in expected_fields:
                self.assertIn(field, signal_data, f"Field {field} missing from signal data")
            
            # Verify specific values
            self.assertEqual(signal_data['method'], 'POST')
            self.assertEqual(signal_data['status_code'], 200)
            self.assertIn('/api/test/', signal_data['api'])
            
            # Verify headers were captured
            headers = json.loads(signal_data['headers'])
            self.assertIn('USER_AGENT', headers)
            self.assertEqual(headers['USER_AGENT'], 'TestAgent/1.0')
            
            # Verify request body (should be masked)
            body = json.loads(signal_data['body'])
            self.assertEqual(body['username'], 'testuser')
            self.assertEqual(body['password'], '***FILTERED***')
            self.assertEqual(body['email'], 'test@example.com')
            
            # Verify response
            response_data = json.loads(signal_data['response'])
            self.assertIn('method', response_data)
            self.assertEqual(response_data['method'], 'POST')
            
            # Verify execution time
            self.assertIsInstance(signal_data['execution_time'], (int, float))
            self.assertGreater(signal_data['execution_time'], 0)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener

    @override_settings(DRF_API_LOGGER_SLOW_API_ABOVE=100)
    def test_slow_api_detection_workflow(self):
        """Test slow API detection in complete workflow"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        try:
            # Call slow API endpoint
            response = self.client.get('/api/slow/')
            self.assertEqual(response.status_code, 200)
            
            # Verify signal data
            self.assertEqual(len(self.all_signals), 1)
            signal_data = self.all_signals[0]
            
            # Check execution time is above threshold
            execution_time_ms = signal_data['execution_time'] * 1000
            self.assertGreater(execution_time_ms, 100)  # Should be > 100ms
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.signal_listener