"""
Test cases for Models and Admin
"""
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.utils import timezone
from django.test.utils import override_settings
from unittest.mock import Mock, patch
from datetime import timedelta
import csv
import io

# Only import models if database logging is enabled
from drf_api_logger.utils import database_log_enabled


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestModels(TestCase):
    """Test cases for API Logger models"""

    def setUp(self):
        """Set up test fixtures"""
        if database_log_enabled():
            from drf_api_logger.models import APILogsModel
            self.APILogsModel = APILogsModel

    def test_model_creation(self):
        """Test creating an API log model instance"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        log = self.APILogsModel(
            api='/api/test/',
            headers='{"Content-Type": "application/json"}',
            body='{"test": "data"}',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{"result": "success"}',
            status_code=200,
            execution_time=0.123,
            added_on=timezone.now()
        )
        log.save()
        
        self.assertIsNotNone(log.id)
        self.assertEqual(log.api, '/api/test/')
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)

    def test_model_string_representation(self):
        """Test the string representation of the model"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        log = self.APILogsModel(
            api='/api/users/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='192.168.1.1',
            response='[]',
            status_code=200,
            execution_time=0.05,
            added_on=timezone.now()
        )
        
        self.assertEqual(str(log), '/api/users/')

    def test_model_ordering(self):
        """Test that models are ordered by added_on descending"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        # Create logs with different timestamps
        now = timezone.now()
        log1 = self.APILogsModel.objects.create(
            api='/api/1/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=now - timedelta(hours=2)
        )
        
        log2 = self.APILogsModel.objects.create(
            api='/api/2/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=now
        )
        
        logs = self.APILogsModel.objects.all()
        self.assertEqual(logs[0], log2)  # Most recent first
        self.assertEqual(logs[1], log1)

    def test_model_field_types(self):
        """Test that model fields have correct types"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        log = self.APILogsModel(
            api='/api/test/',
            headers='{"test": "header"}',
            body='{"test": "body"}',
            method='POST',
            client_ip_address='10.0.0.1',
            response='{"test": "response"}',
            status_code=201,
            execution_time=1.234,
            added_on=timezone.now()
        )
        log.save()
        
        # Check field types
        self.assertIsInstance(log.api, str)
        self.assertIsInstance(log.headers, str)
        self.assertIsInstance(log.body, str)
        self.assertIsInstance(log.method, str)
        self.assertIsInstance(log.client_ip_address, str)
        self.assertIsInstance(log.response, str)
        self.assertIsInstance(log.status_code, int)
        self.assertIsInstance(log.execution_time, (float, int))

    def test_model_max_lengths(self):
        """Test model field max lengths"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        # Test long API URL (should be truncated or handled)
        long_api = '/api/' + 'x' * 1020  # Total 1025 chars
        log = self.APILogsModel(
            api=long_api[:1024],  # Truncate to max length
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=timezone.now()
        )
        log.save()
        
        self.assertEqual(len(log.api), 1024)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestAdmin(TestCase):
    """Test cases for API Logger admin interface"""

    def setUp(self):
        """Set up test fixtures"""
        if database_log_enabled():
            from drf_api_logger.models import APILogsModel
            from drf_api_logger.admin import APILogsAdmin
            
            self.APILogsModel = APILogsModel
            self.APILogsAdmin = APILogsAdmin
            
            self.site = AdminSite()
            self.admin = self.APILogsAdmin(self.APILogsModel, self.site)
            self.factory = RequestFactory()
            self.user = User.objects.create_superuser(
                username='admin',
                email='admin@test.com',
                password='password'
            )

    def test_admin_registration(self):
        """Test that the model is registered with admin"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        self.assertIsNotNone(self.admin)

    def test_admin_list_display(self):
        """Test admin list display fields"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        expected_fields = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time')
        self.assertEqual(self.admin.list_display, expected_fields)

    def test_admin_list_filter(self):
        """Test admin list filter fields"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        expected_filters = ('added_on', 'status_code', 'method')
        for filter_field in expected_filters:
            self.assertIn(filter_field, self.admin.list_filter)

    def test_admin_search_fields(self):
        """Test admin search fields"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        expected_search = ('body', 'response', 'headers', 'api')
        self.assertEqual(self.admin.search_fields, expected_search)

    def test_admin_readonly_fields(self):
        """Test admin readonly fields"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        readonly = self.admin.readonly_fields
        self.assertIn('execution_time', readonly)
        self.assertIn('client_ip_address', readonly)
        self.assertIn('api', readonly)

    def test_admin_has_add_permission(self):
        """Test that add permission is disabled"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        request = self.factory.get('/admin/')
        request.user = self.user
        self.assertFalse(self.admin.has_add_permission(request))

    def test_admin_has_change_permission(self):
        """Test that change permission is disabled"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        request = self.factory.get('/admin/')
        request.user = self.user
        self.assertFalse(self.admin.has_change_permission(request))

    @override_settings(DRF_API_LOGGER_TIMEDELTA=330)
    def test_admin_added_on_time_with_timedelta(self):
        """Test added_on_time method with timedelta setting"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        from drf_api_logger.admin import APILogsAdmin
        
        admin = APILogsAdmin(self.APILogsModel, self.site)
        
        now = timezone.now()
        log = self.APILogsModel(
            api='/api/test/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=now
        )
        
        # Test with timedelta
        formatted_time = admin.added_on_time(log)
        self.assertIsNotNone(formatted_time)
        self.assertIsInstance(formatted_time, str)

    def test_admin_export_csv_action(self):
        """Test CSV export functionality"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        # Create a test log
        log = self.APILogsModel.objects.create(
            api='/api/export/',
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=timezone.now()
        )
        
        request = self.factory.get('/admin/')
        request.user = self.user
        
        queryset = self.APILogsModel.objects.filter(id=log.id)
        response = self.admin.export_as_csv(request, queryset)
        
        # Check response is CSV
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)
        
        # Should have header and at least one data row
        self.assertGreaterEqual(len(rows), 2)

    @override_settings(DRF_API_LOGGER_SLOW_API_ABOVE=100)
    def test_admin_slow_api_filter(self):
        """Test slow API filter in admin"""
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
            
        from drf_api_logger.admin import APILogsAdmin, SlowAPIsFilter
        
        # Re-initialize admin with slow API setting
        admin = APILogsAdmin(self.APILogsModel, self.site)
        
        # Check that SlowAPIsFilter is in list_filter
        self.assertIn(SlowAPIsFilter, admin.list_filter)