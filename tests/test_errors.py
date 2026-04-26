"""
Test cases for error highlighting, grouping, and frequency tracking.
"""
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.test.utils import override_settings
from django.utils import timezone

from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware


class TestErrorTypeExtraction(TestCase):

    def setUp(self):
        self.middleware = APILoggerMiddleware(get_response=Mock())

    def test_extract_from_detail_field(self):
        body = {'detail': 'Not found.'}
        result = self.middleware._extract_error_type(body, 404)
        self.assertEqual(result, 'Not found.')

    def test_extract_from_code_field(self):
        body = {'code': 'token_not_valid'}
        result = self.middleware._extract_error_type(body, 401)
        self.assertEqual(result, 'token_not_valid')

    def test_detail_takes_precedence_over_code(self):
        body = {'detail': 'Authentication failed', 'code': 'auth_error'}
        result = self.middleware._extract_error_type(body, 401)
        self.assertEqual(result, 'Authentication failed')

    def test_fallback_to_status_map(self):
        result = self.middleware._extract_error_type({}, 404)
        self.assertEqual(result, 'NotFound')

    def test_fallback_400(self):
        result = self.middleware._extract_error_type({}, 400)
        self.assertEqual(result, 'BadRequest')

    def test_fallback_401(self):
        result = self.middleware._extract_error_type({}, 401)
        self.assertEqual(result, 'Unauthorized')

    def test_fallback_403(self):
        result = self.middleware._extract_error_type({}, 403)
        self.assertEqual(result, 'Forbidden')

    def test_fallback_429(self):
        result = self.middleware._extract_error_type({}, 429)
        self.assertEqual(result, 'Throttled')

    def test_fallback_500(self):
        result = self.middleware._extract_error_type({}, 500)
        self.assertEqual(result, 'InternalServerError')

    def test_fallback_503(self):
        result = self.middleware._extract_error_type({}, 503)
        self.assertEqual(result, 'ServiceUnavailable')

    def test_unknown_status_code(self):
        result = self.middleware._extract_error_type({}, 418)
        self.assertEqual(result, 'HTTP418')

    def test_string_response_body(self):
        result = self.middleware._extract_error_type('plain error', 500)
        self.assertEqual(result, 'InternalServerError')

    def test_list_response_body(self):
        result = self.middleware._extract_error_type(['error1'], 400)
        self.assertEqual(result, 'BadRequest')

    def test_long_detail_truncated(self):
        body = {'detail': 'x' * 500}
        result = self.middleware._extract_error_type(body, 400)
        self.assertEqual(len(result), 256)


class TestMiddlewareErrorCapture(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _make_response(self, status, body):
        return HttpResponse(
            json.dumps(body),
            content_type='application/json',
            status=status
        )

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_error_type_in_signal_for_4xx(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        def get_response(request):
            return self._make_response(404, {'detail': 'Not found.'})

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=get_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            self.assertEqual(signal_data[0]['error_type'], 'Not found.')
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_error_type_in_signal_for_500(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        def get_response(request):
            return self._make_response(500, {'detail': 'Internal server error'})

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=get_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            self.assertEqual(signal_data[0]['error_type'], 'Internal server error')
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_no_error_type_for_2xx(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        def get_response(request):
            return self._make_response(200, {'ok': True})

        signal_data = []
        from drf_api_logger import API_LOGGER_SIGNAL
        def listener(**kwargs):
            signal_data.append(kwargs)

        API_LOGGER_SIGNAL.listen += listener
        try:
            middleware = APILoggerMiddleware(get_response=get_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            self.assertEqual(len(signal_data), 1)
            self.assertNotIn('error_type', signal_data[0])
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_DATABASE=True,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    @patch('drf_api_logger.middleware.api_logger_middleware.LOGGER_THREAD')
    def test_error_type_in_db_payload(self, mock_thread, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'
        mock_thread.put_log_data = Mock()

        def get_response(request):
            return self._make_response(403, {'detail': 'Permission denied.'})

        middleware = APILoggerMiddleware(get_response=get_response)
        request = self.factory.get('/api/test/')
        middleware(request)

        mock_thread.put_log_data.assert_called_once()
        call_data = mock_thread.put_log_data.call_args[1]['data']
        self.assertEqual(call_data['error_type'], 'Permission denied.')


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestErrorModelField(TestCase):

    def test_create_log_with_error_type(self):
        from drf_api_logger.models import APILogsModel
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{"detail": "Not found."}',
            status_code=404, execution_time=0.01, added_on=timezone.now(),
            error_type='Not found.',
        )
        self.assertEqual(log.error_type, 'Not found.')

    def test_create_log_without_error_type(self):
        from drf_api_logger.models import APILogsModel
        log = APILogsModel.objects.create(
            api='/api/test/', headers='{}', body='', method='GET',
            client_ip_address='127.0.0.1', response='{}',
            status_code=200, execution_time=0.01, added_on=timezone.now(),
        )
        self.assertIsNone(log.error_type)

    def test_error_type_indexed(self):
        from drf_api_logger.models import APILogsModel
        field = APILogsModel._meta.get_field('error_type')
        self.assertTrue(field.db_index)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestErrorGrouping(TestCase):

    def setUp(self):
        from drf_api_logger.models import APILogsModel
        self.APILogsModel = APILogsModel
        now = timezone.now()

        for i in range(5):
            APILogsModel.objects.create(
                api='/api/users/', headers='{}', body='', method='GET',
                client_ip_address='127.0.0.1', response='{}',
                status_code=404, execution_time=0.01, added_on=now,
                error_type='Not found.',
            )
        for i in range(3):
            APILogsModel.objects.create(
                api='/api/orders/', headers='{}', body='', method='POST',
                client_ip_address='127.0.0.1', response='{}',
                status_code=400, execution_time=0.02, added_on=now,
                error_type='BadRequest',
            )
        for i in range(2):
            APILogsModel.objects.create(
                api='/api/users/', headers='{}', body='', method='POST',
                client_ip_address='127.0.0.1', response='{}',
                status_code=500, execution_time=1.5, added_on=now,
                error_type='InternalServerError',
            )

    def test_group_by_endpoint(self):
        from django.db.models import Count
        groups = list(
            self.APILogsModel.objects.filter(status_code__gte=400)
            .values('api', 'status_code', 'error_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0]['api'], '/api/users/')
        self.assertEqual(groups[0]['status_code'], 404)
        self.assertEqual(groups[0]['count'], 5)

    def test_group_by_error_type(self):
        from django.db.models import Count
        groups = list(
            self.APILogsModel.objects.filter(status_code__gte=400)
            .values('error_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0]['error_type'], 'Not found.')
        self.assertEqual(groups[0]['count'], 5)

    def test_error_rate(self):
        total = self.APILogsModel.objects.count()
        errors = self.APILogsModel.objects.filter(status_code__gte=400).count()
        rate = round((errors / total) * 100, 1)
        self.assertEqual(errors, 10)
        self.assertEqual(total, 10)
        self.assertEqual(rate, 100.0)
