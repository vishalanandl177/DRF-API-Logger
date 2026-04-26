"""
Test cases for Prometheus-style metrics.
"""
import json
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.test.utils import override_settings

from drf_api_logger.metrics import (
    record_request, get_metrics, format_prometheus, reset_metrics,
)
from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware


class TestMetricsRecording(TestCase):

    def setUp(self):
        reset_metrics()

    def tearDown(self):
        reset_metrics()

    def test_record_single_request(self):
        record_request({
            'method': 'GET', 'api': '/api/users/', 'status_code': 200,
            'execution_time': 0.05,
        })
        m = get_metrics()
        self.assertEqual(m['counters']['request_total'], 1)
        self.assertEqual(m['counters']['status_2xx'], 1)
        self.assertEqual(m['counters']['error_total'], 0)

    def test_record_multiple_requests(self):
        for _ in range(10):
            record_request({
                'method': 'GET', 'api': '/api/users/', 'status_code': 200,
                'execution_time': 0.01,
            })
        m = get_metrics()
        self.assertEqual(m['counters']['request_total'], 10)

    def test_status_code_buckets(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})
        record_request({'method': 'GET', 'api': '/', 'status_code': 301, 'execution_time': 0.01})
        record_request({'method': 'GET', 'api': '/', 'status_code': 404, 'execution_time': 0.01})
        record_request({'method': 'GET', 'api': '/', 'status_code': 500, 'execution_time': 0.01})
        m = get_metrics()
        self.assertEqual(m['counters']['status_2xx'], 1)
        self.assertEqual(m['counters']['status_3xx'], 1)
        self.assertEqual(m['counters']['status_4xx'], 1)
        self.assertEqual(m['counters']['status_5xx'], 1)
        self.assertEqual(m['counters']['error_total'], 2)

    def test_latency_tracking(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.1})
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.3})
        m = get_metrics()
        self.assertEqual(m['latency']['total_requests'], 2)
        self.assertAlmostEqual(m['latency']['avg_ms'], 200.0, places=1)
        self.assertAlmostEqual(m['latency']['max_ms'], 300.0, places=1)

    def test_per_method_tracking(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})
        record_request({'method': 'POST', 'api': '/', 'status_code': 201, 'execution_time': 0.01})
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})
        m = get_metrics()
        self.assertEqual(m['per_method']['GET'], 2)
        self.assertEqual(m['per_method']['POST'], 1)

    def test_per_endpoint_tracking(self):
        record_request({'method': 'GET', 'api': '/api/users/?page=1', 'status_code': 200, 'execution_time': 0.05})
        record_request({'method': 'GET', 'api': '/api/users/?page=2', 'status_code': 200, 'execution_time': 0.07})
        record_request({'method': 'GET', 'api': '/api/orders/', 'status_code': 404, 'execution_time': 0.01})
        m = get_metrics()
        self.assertEqual(m['per_endpoint']['/api/users/']['count'], 2)
        self.assertEqual(m['per_endpoint']['/api/orders/']['count'], 1)
        self.assertEqual(m['per_endpoint']['/api/orders/']['errors'], 1)

    def test_per_error_type_tracking(self):
        record_request({
            'method': 'GET', 'api': '/', 'status_code': 404,
            'execution_time': 0.01, 'error_type': 'NotFound',
        })
        record_request({
            'method': 'POST', 'api': '/', 'status_code': 400,
            'execution_time': 0.01, 'error_type': 'BadRequest',
        })
        record_request({
            'method': 'GET', 'api': '/', 'status_code': 404,
            'execution_time': 0.01, 'error_type': 'NotFound',
        })
        m = get_metrics()
        self.assertEqual(m['per_error_type']['NotFound'], 2)
        self.assertEqual(m['per_error_type']['BadRequest'], 1)

    def test_error_rate(self):
        for _ in range(8):
            record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})
        for _ in range(2):
            record_request({'method': 'GET', 'api': '/', 'status_code': 500, 'execution_time': 0.01})
        m = get_metrics()
        self.assertEqual(m['error_rate_pct'], 20.0)

    def test_reset_metrics(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})
        reset_metrics()
        m = get_metrics()
        self.assertEqual(m['counters']['request_total'], 0)
        self.assertEqual(m['latency']['total_requests'], 0)
        self.assertEqual(m['per_method'], {})
        self.assertEqual(m['per_endpoint'], {})


class TestPrometheusFormat(TestCase):

    def setUp(self):
        reset_metrics()

    def tearDown(self):
        reset_metrics()

    def test_format_empty(self):
        output = format_prometheus()
        self.assertIn('drf_api_requests_total 0', output)
        self.assertIn('drf_api_errors_total 0', output)

    def test_format_with_data(self):
        record_request({
            'method': 'GET', 'api': '/api/users/', 'status_code': 200,
            'execution_time': 0.15,
        })
        record_request({
            'method': 'POST', 'api': '/api/users/', 'status_code': 400,
            'execution_time': 0.02, 'error_type': 'BadRequest',
        })
        output = format_prometheus()
        self.assertIn('drf_api_requests_total 2', output)
        self.assertIn('drf_api_errors_total 1', output)
        self.assertIn('drf_api_latency_avg_ms', output)
        self.assertIn('drf_api_latency_max_ms', output)
        self.assertIn('method="GET"', output)
        self.assertIn('method="POST"', output)
        self.assertIn('type="BadRequest"', output)
        self.assertIn('endpoint="/api/users/"', output)
        self.assertIn('# HELP', output)
        self.assertIn('# TYPE', output)


class TestMetricsViews(TestCase):

    def setUp(self):
        reset_metrics()
        self.factory = RequestFactory()

    def tearDown(self):
        reset_metrics()

    def test_json_view(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})

        from drf_api_logger.views import metrics_json
        request = self.factory.get('/drf-api-logger/metrics/json/')
        response = metrics_json(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = json.loads(response.content)
        self.assertEqual(data['counters']['request_total'], 1)

    def test_prometheus_view(self):
        record_request({'method': 'GET', 'api': '/', 'status_code': 200, 'execution_time': 0.01})

        from drf_api_logger.views import metrics_prometheus
        request = self.factory.get('/drf-api-logger/metrics/')
        response = metrics_prometheus(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        self.assertIn('drf_api_requests_total 1', response.content.decode())


class TestMiddlewareMetricsIntegration(TestCase):

    def setUp(self):
        reset_metrics()
        self.factory = RequestFactory()

    def tearDown(self):
        reset_metrics()

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_METRICS=True,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_metrics_recorded_on_request(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        def get_response(request):
            return HttpResponse(
                json.dumps({'ok': True}),
                content_type='application/json',
                status=200,
            )

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)
        API_LOGGER_SIGNAL.listen += listener

        try:
            middleware = APILoggerMiddleware(get_response=get_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            m = get_metrics()
            self.assertEqual(m['counters']['request_total'], 1)
            self.assertEqual(m['counters']['status_2xx'], 1)
        finally:
            API_LOGGER_SIGNAL.listen -= listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_ENABLE_METRICS=False,
    )
    @patch('drf_api_logger.middleware.api_logger_middleware.resolve')
    def test_no_metrics_when_disabled(self, mock_resolve):
        mock_resolve.return_value.namespace = None
        mock_resolve.return_value.url_name = 'test'

        def get_response(request):
            return HttpResponse(
                json.dumps({'ok': True}),
                content_type='application/json',
                status=200,
            )

        from drf_api_logger import API_LOGGER_SIGNAL
        signal_data = []
        def listener(**kwargs):
            signal_data.append(kwargs)
        API_LOGGER_SIGNAL.listen += listener

        try:
            middleware = APILoggerMiddleware(get_response=get_response)
            request = self.factory.get('/api/test/')
            middleware(request)

            m = get_metrics()
            self.assertEqual(m['counters']['request_total'], 0)
        finally:
            API_LOGGER_SIGNAL.listen -= listener
