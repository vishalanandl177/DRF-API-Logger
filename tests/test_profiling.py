"""
Test cases for the API profiling feature.
Covers: middleware profiling instrumentation, SQL tracking, profiling data structure,
signal payload, admin display, diagnosis hints, and HighQueryCountFilter.
"""
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.test.utils import override_settings
from django.utils import timezone

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware
from drf_api_logger.utils import profiling_enabled


class TestProfilingEnabled(TestCase):

    @override_settings(DRF_API_LOGGER_ENABLE_PROFILING=False)
    def test_profiling_disabled(self):
        self.assertFalse(profiling_enabled())

    @override_settings(DRF_API_LOGGER_ENABLE_PROFILING=True)
    def test_profiling_enabled(self):
        self.assertTrue(profiling_enabled())


class TestMiddlewareProfilingInit(TestCase):

    def test_profiling_defaults_false(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertFalse(middleware.DRF_API_LOGGER_ENABLE_PROFILING)
        self.assertTrue(middleware.DRF_API_LOGGER_PROFILING_SQL_TRACKING)

    @override_settings(DRF_API_LOGGER_ENABLE_PROFILING=True)
    def test_profiling_enabled_from_settings(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_ENABLE_PROFILING)

    @override_settings(
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=False
    )
    def test_sql_tracking_disabled(self):
        middleware = APILoggerMiddleware(get_response=Mock())
        self.assertTrue(middleware.DRF_API_LOGGER_ENABLE_PROFILING)
        self.assertFalse(middleware.DRF_API_LOGGER_PROFILING_SQL_TRACKING)


class TestMiddlewareProfilingInstrumentation(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def get_json_response(self, request):
        return HttpResponse(
            json.dumps({"message": "ok"}),
            content_type="application/json",
            status=200
        )

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_profiling_data_in_signal(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            data = signal_data[0]

            self.assertIn('profiling_data', data)
            profiling = data['profiling_data']
            self.assertIn('middleware_before_view', profiling)
            self.assertIn('view_and_serialization', profiling)
            self.assertIn('middleware_after_view', profiling)
            self.assertIn('sql', profiling)
            self.assertIn('total_time', profiling['sql'])
            self.assertIn('query_count', profiling['sql'])

            self.assertIn('sql_query_count', data)
            self.assertIsInstance(data['sql_query_count'], int)
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=False
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_profiling_without_sql_tracking(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            profiling = signal_data[0]['profiling_data']

            self.assertIn('middleware_before_view', profiling)
            self.assertIn('view_and_serialization', profiling)
            self.assertIn('middleware_after_view', profiling)
            self.assertNotIn('sql', profiling)
            self.assertIsNone(signal_data[0]['sql_query_count'])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=False
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_no_profiling_when_disabled(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            self.assertNotIn('profiling_data', signal_data[0])
            self.assertNotIn('sql_query_count', signal_data[0])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_profiling_timing_values_are_positive(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            profiling = signal_data[0]['profiling_data']
            self.assertGreaterEqual(profiling['middleware_before_view'], 0)
            self.assertGreaterEqual(profiling['view_and_serialization'], 0)
            self.assertGreaterEqual(profiling['middleware_after_view'], 0)
            self.assertGreaterEqual(profiling['sql']['total_time'], 0)
            self.assertGreaterEqual(profiling['sql']['query_count'], 0)
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.middleware.api_logger_middleware.LOGGER_THREAD')
    def test_profiling_data_serialized_for_db(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        mock_thread.put_log_data = Mock()

        middleware = APILoggerMiddleware(get_response=self.get_json_response)
        request = self.factory.get('/api/test/')
        middleware(request)

        mock_thread.put_log_data.assert_called_once()
        call_data = mock_thread.put_log_data.call_args[1]['data']

        self.assertIn('profiling_data', call_data)
        self.assertIsInstance(call_data['profiling_data'], str)

        parsed = json.loads(call_data['profiling_data'])
        self.assertIn('middleware_before_view', parsed)
        self.assertIn('view_and_serialization', parsed)
        self.assertIn('sql', parsed)

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_PROFILING=True,
        DRF_API_LOGGER_PROFILING_SQL_TRACKING=True
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_sql_reset_queries_called(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=self.get_json_response)

            with patch('django.db.reset_queries') as mock_reset:
                request = self.factory.get('/api/test/')
                middleware(request)
                self.assertEqual(mock_reset.call_count, 2)
        finally:
            API_LOGGER_SIGNAL.listen -= listener


class TestProfilingDiagnosis(TestCase):
    """Test the diagnosis hint generation logic (pure function, no DB needed)."""

    def test_n_plus_1_diagnosis(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {
            'view_and_serialization': 1.0,
            'sql': {'total_time': 0.8, 'query_count': 47},
        }
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIn('N+1', diagnosis)

    def test_slow_queries_diagnosis(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {
            'view_and_serialization': 1.0,
            'sql': {'total_time': 0.9, 'query_count': 3},
        }
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIn('slow queries', diagnosis)

    def test_business_logic_diagnosis(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {
            'view_and_serialization': 2.0,
            'sql': {'total_time': 0.1, 'query_count': 3},
        }
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIn('business logic', diagnosis)

    def test_high_middleware_diagnosis(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {
            'middleware_before_view': 0.3,
            'view_and_serialization': 0.5,
            'middleware_after_view': 0.3,
            'sql': {'total_time': 0.1, 'query_count': 1},
        }
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIn('Middleware overhead', diagnosis)

    def test_no_diagnosis_for_normal_request(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {
            'middleware_before_view': 0.001,
            'view_and_serialization': 0.05,
            'middleware_after_view': 0.001,
            'sql': {'total_time': 0.02, 'query_count': 3},
        }
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIsNone(diagnosis)

    def test_no_diagnosis_zero_total(self):
        from drf_api_logger.admin import _get_profiling_diagnosis
        profiling = {'view_and_serialization': 0}
        diagnosis = _get_profiling_diagnosis(profiling)
        self.assertIsNone(diagnosis)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestHighQueryCountFilter(TestCase):

    def setUp(self):
        from drf_api_logger.utils import database_log_enabled
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
        from drf_api_logger.models import APILogsModel
        self.APILogsModel = APILogsModel
        self.now = timezone.now()

        self.log_high = APILogsModel.objects.create(
            api='/api/high/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=1.0, added_on=self.now,
            sql_query_count=15,
        )
        self.log_moderate = APILogsModel.objects.create(
            api='/api/mod/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.5, added_on=self.now,
            sql_query_count=7,
        )
        self.log_low = APILogsModel.objects.create(
            api='/api/low/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=self.now,
            sql_query_count=2,
        )
        self.log_none = APILogsModel.objects.create(
            api='/api/none/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=self.now,
            sql_query_count=None,
        )

    def test_filter_high(self):
        from drf_api_logger.admin import HighQueryCountFilter
        qs = self.APILogsModel.objects.all()
        f = HighQueryCountFilter(None, {'sql_queries': ['high']}, self.APILogsModel, None)
        result = f.queryset(None, qs)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().api, '/api/high/')

    def test_filter_moderate(self):
        from drf_api_logger.admin import HighQueryCountFilter
        qs = self.APILogsModel.objects.all()
        f = HighQueryCountFilter(None, {'sql_queries': ['moderate']}, self.APILogsModel, None)
        result = f.queryset(None, qs)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().api, '/api/mod/')

    def test_filter_low(self):
        from drf_api_logger.admin import HighQueryCountFilter
        qs = self.APILogsModel.objects.all()
        f = HighQueryCountFilter(None, {'sql_queries': ['low']}, self.APILogsModel, None)
        result = f.queryset(None, qs)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().api, '/api/low/')

    def test_filter_none(self):
        from drf_api_logger.admin import HighQueryCountFilter
        qs = self.APILogsModel.objects.all()
        f = HighQueryCountFilter(None, {'sql_queries': ['none']}, self.APILogsModel, None)
        result = f.queryset(None, qs)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().api, '/api/none/')

    def test_filter_all(self):
        from drf_api_logger.admin import HighQueryCountFilter
        qs = self.APILogsModel.objects.all()
        f = HighQueryCountFilter(None, {}, self.APILogsModel, None)
        result = f.queryset(None, qs)
        self.assertEqual(result.count(), 4)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestProfilingModelFields(TestCase):

    def setUp(self):
        from drf_api_logger.utils import database_log_enabled
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")

    def test_create_log_with_profiling_data(self):
        from drf_api_logger.models import APILogsModel
        profiling = json.dumps({
            'middleware_before_view': 0.001,
            'view_and_serialization': 0.5,
            'middleware_after_view': 0.002,
            'sql': {'total_time': 0.3, 'query_count': 12},
        })
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.503, added_on=timezone.now(),
            profiling_data=profiling, sql_query_count=12,
        )
        self.assertEqual(log.sql_query_count, 12)
        parsed = json.loads(log.profiling_data)
        self.assertEqual(parsed['sql']['query_count'], 12)

    def test_create_log_without_profiling_data(self):
        from drf_api_logger.models import APILogsModel
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=timezone.now(),
        )
        self.assertIsNone(log.profiling_data)
        self.assertIsNone(log.sql_query_count)

    def test_profiling_fields_nullable(self):
        from drf_api_logger.models import APILogsModel
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=timezone.now(),
            profiling_data=None, sql_query_count=None,
        )
        log.refresh_from_db()
        self.assertIsNone(log.profiling_data)
        self.assertIsNone(log.sql_query_count)


@override_settings(
    DRF_API_LOGGER_DATABASE=True,
    DRF_API_LOGGER_ENABLE_PROFILING=True,
)
class TestProfilingAdminDisplay(TestCase):

    def setUp(self):
        from drf_api_logger.utils import database_log_enabled
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")
        from drf_api_logger.models import APILogsModel
        from drf_api_logger.admin import APILogsAdmin
        from django.contrib.admin.sites import AdminSite

        self.APILogsModel = APILogsModel
        self.site = AdminSite()
        self.admin = APILogsAdmin(APILogsModel, self.site)

    def test_profiling_breakdown_with_data(self):
        profiling = json.dumps({
            'middleware_before_view': 0.001,
            'view_and_serialization': 1.0,
            'middleware_after_view': 0.002,
            'sql': {'total_time': 0.8, 'query_count': 47},
        })
        log = self.APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=1.003, added_on=timezone.now(),
            profiling_data=profiling, sql_query_count=47,
        )
        html = self.admin.profiling_breakdown(log)
        self.assertIn('View + Serialization', str(html))
        self.assertIn('SQL Total Time', str(html))
        self.assertIn('N+1', str(html))

    def test_profiling_breakdown_without_data(self):
        log = self.APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=timezone.now(),
        )
        result = self.admin.profiling_breakdown(log)
        self.assertEqual(result, '-')

    def test_profiling_breakdown_invalid_json(self):
        log = self.APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.1, added_on=timezone.now(),
            profiling_data='not valid json',
        )
        result = self.admin.profiling_breakdown(log)
        self.assertEqual(result, '-')

    def test_admin_list_display_includes_sql_query_count(self):
        self.assertIn('sql_query_count', self.admin.list_display)

    def test_admin_readonly_includes_profiling_breakdown(self):
        self.assertIn('profiling_breakdown', self.admin.readonly_fields)

    def test_admin_list_filter_includes_query_filter(self):
        from drf_api_logger.admin import HighQueryCountFilter
        self.assertIn(HighQueryCountFilter, self.admin.list_filter)
