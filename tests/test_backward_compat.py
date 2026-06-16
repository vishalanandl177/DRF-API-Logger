"""
Backward compatibility tests.
Ensures that when profiling is disabled (default), behavior is identical
to the pre-profiling version of the package.
"""
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.test.utils import override_settings
from django.utils import timezone

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware
from drf_api_logger import API_LOGGER_SIGNAL


class TestBackwardCompatMiddleware(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def get_json_response(self, request):
        return HttpResponse(
            json.dumps({"ok": True}),
            content_type="application/json",
            status=200
        )

    @override_settings(DRF_API_LOGGER_SIGNAL=True, DRF_API_LOGGER_ENABLE_PROFILING=False)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_signal_payload_unchanged(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            data = signal_data[0]

            for key in ('api', 'headers', 'body', 'method', 'client_ip_address',
                        'response', 'status_code', 'execution_time', 'added_on'):
                self.assertIn(key, data)

            self.assertNotIn('profiling_data', data)
            self.assertNotIn('sql_query_count', data)
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_ENABLE_PROFILING=False
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.apps.LOGGER_THREAD')
    def test_db_payload_unchanged(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        mock_thread.put_log_data = Mock()

        middleware = APILoggerMiddleware(get_response=self.get_json_response)
        request = self.factory.get('/api/test/')
        middleware(request)

        mock_thread.put_log_data.assert_called_once()
        call_data = mock_thread.put_log_data.call_args[1]['data']

        self.assertNotIn('profiling_data', call_data)
        self.assertNotIn('sql_query_count', call_data)

    @override_settings(DRF_API_LOGGER_SIGNAL=True, DRF_API_LOGGER_ENABLE_PROFILING=False)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_no_sql_tracking_overhead(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)
            self.assertEqual(len(signal_data), 1)
        finally:
            API_LOGGER_SIGNAL.listen -= listener


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestBackwardCompatModel(TestCase):

    def setUp(self):
        from drf_api_logger.utils import database_log_enabled
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")

    def test_old_style_create(self):
        from drf_api_logger.models import APILogsModel
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=timezone.now(),
        )
        log.refresh_from_db()
        self.assertIsNone(log.profiling_data)
        self.assertIsNone(log.sql_query_count)
        self.assertEqual(log.api, '/api/test/')

    def test_mixed_data_query(self):
        from drf_api_logger.models import APILogsModel
        now = timezone.now()

        APILogsModel.objects.create(
            api='/api/old/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=now,
        )
        APILogsModel.objects.create(
            api='/api/new/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.5, added_on=now,
            profiling_data='{"sql": {"query_count": 5}}', sql_query_count=5,
        )

        all_logs = APILogsModel.objects.all()
        self.assertEqual(all_logs.count(), 2)

        profiled = APILogsModel.objects.filter(sql_query_count__isnull=False)
        self.assertEqual(profiled.count(), 1)

        not_profiled = APILogsModel.objects.filter(sql_query_count__isnull=True)
        self.assertEqual(not_profiled.count(), 1)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestBackwardCompatAdmin(TestCase):

    def setUp(self):
        from drf_api_logger.utils import database_log_enabled
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")

    def test_admin_list_display_unchanged(self):
        from drf_api_logger.admin import APILogsAdmin
        from drf_api_logger.models import APILogsModel
        from django.contrib.admin.sites import AdminSite

        admin = APILogsAdmin(APILogsModel, AdminSite())
        expected = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time')
        self.assertEqual(admin.list_display, expected)

    def test_admin_readonly_fields_unchanged(self):
        from drf_api_logger.admin import APILogsAdmin
        from drf_api_logger.models import APILogsModel
        from django.contrib.admin.sites import AdminSite

        admin = APILogsAdmin(APILogsModel, AdminSite())
        # headers/body/response are rendered through prettified, syntax-highlighted
        # readonly methods instead of the raw model fields (which are excluded).
        expected = (
            'execution_time', 'client_ip_address', 'api',
            'headers_prettified', 'body_prettified', 'method', 'response_prettified',
            'status_code', 'added_on_time',
        )
        self.assertEqual(admin.readonly_fields, expected)
        self.assertNotIn('profiling_breakdown', admin.readonly_fields)
        for raw_field in ('headers', 'body', 'response'):
            self.assertIn(raw_field, admin.exclude)

    @override_settings(DRF_API_LOGGER_ENABLE_PROFILING=True)
    def test_admin_with_profiling_enabled(self):
        from drf_api_logger.admin import APILogsAdmin, HighQueryCountFilter
        from drf_api_logger.models import APILogsModel
        from django.contrib.admin.sites import AdminSite

        admin = APILogsAdmin(APILogsModel, AdminSite())
        self.assertIn('sql_query_count', admin.list_display)
        self.assertIn('profiling_breakdown', admin.readonly_fields)
        self.assertIn(HighQueryCountFilter, admin.list_filter)


class TestBackwardCompatSettings(TestCase):

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    def test_database_only(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_DATABASE)
        self.assertFalse(middleware.DRF_API_LOGGER_SIGNAL)
        self.assertFalse(middleware.DRF_API_LOGGER_ENABLE_PROFILING)

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    def test_signal_only(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertFalse(middleware.DRF_API_LOGGER_DATABASE)
        self.assertTrue(middleware.DRF_API_LOGGER_SIGNAL)
        self.assertFalse(middleware.DRF_API_LOGGER_ENABLE_PROFILING)

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_PATH_TYPE='FULL_PATH',
        DRF_API_LOGGER_METHODS=['GET'],
        DRF_API_LOGGER_STATUS_CODES=[200],
        DRF_API_LOGGER_ENABLE_TRACING=True,
    )
    def test_all_existing_settings(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertEqual(middleware.DRF_API_LOGGER_PATH_TYPE, 'FULL_PATH')
        self.assertEqual(middleware.DRF_API_LOGGER_METHODS, ['GET'])
        self.assertEqual(middleware.DRF_API_LOGGER_STATUS_CODES, [200])
        self.assertTrue(middleware.DRF_API_LOGGER_ENABLE_TRACING)
        self.assertFalse(middleware.DRF_API_LOGGER_ENABLE_PROFILING)
