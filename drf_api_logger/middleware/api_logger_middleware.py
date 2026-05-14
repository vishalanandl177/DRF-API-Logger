import importlib
import json
import random
import time
import uuid

from django.conf import settings
from django.urls import resolve
from django.utils import timezone
from datetime import datetime

from drf_api_logger import apps as logger_apps
from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.utils import get_headers, get_client_ip, mask_sensitive_data


DEFAULT_MAX_REQUEST_BODY_SIZE = 32768
DEFAULT_MAX_RESPONSE_BODY_SIZE = 65536


class APILoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

        self.DRF_API_LOGGER_DATABASE = False
        if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
            self.DRF_API_LOGGER_DATABASE = settings.DRF_API_LOGGER_DATABASE

        self.DRF_API_LOGGER_SIGNAL = False
        if hasattr(settings, 'DRF_API_LOGGER_SIGNAL'):
            self.DRF_API_LOGGER_SIGNAL = settings.DRF_API_LOGGER_SIGNAL

        self.DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'
        if hasattr(settings, 'DRF_API_LOGGER_PATH_TYPE'):
            if settings.DRF_API_LOGGER_PATH_TYPE in ['ABSOLUTE', 'RAW_URI', 'FULL_PATH']:
                self.DRF_API_LOGGER_PATH_TYPE = settings.DRF_API_LOGGER_PATH_TYPE

        self.DRF_API_LOGGER_SKIP_URL_NAME = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_URL_NAME'):
            if type(settings.DRF_API_LOGGER_SKIP_URL_NAME) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_URL_NAME) is list:
                self.DRF_API_LOGGER_SKIP_URL_NAME = settings.DRF_API_LOGGER_SKIP_URL_NAME

        self.DRF_API_LOGGER_SKIP_NAMESPACE = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_NAMESPACE'):
            if type(settings.DRF_API_LOGGER_SKIP_NAMESPACE) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_NAMESPACE) is list:
                self.DRF_API_LOGGER_SKIP_NAMESPACE = settings.DRF_API_LOGGER_SKIP_NAMESPACE

        self.DRF_API_LOGGER_METHODS = []
        if hasattr(settings, 'DRF_API_LOGGER_METHODS'):
            if type(settings.DRF_API_LOGGER_METHODS) is tuple or type(
                    settings.DRF_API_LOGGER_METHODS) is list:
                self.DRF_API_LOGGER_METHODS = settings.DRF_API_LOGGER_METHODS

        self.DRF_API_LOGGER_STATUS_CODES = []
        if hasattr(settings, 'DRF_API_LOGGER_STATUS_CODES'):
            if type(settings.DRF_API_LOGGER_STATUS_CODES) is tuple or type(
                    settings.DRF_API_LOGGER_STATUS_CODES) is list:
                self.DRF_API_LOGGER_STATUS_CODES = settings.DRF_API_LOGGER_STATUS_CODES

        self.DRF_API_LOGGER_ENABLE_TRACING = False
        self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME = None
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_TRACING'):
            self.DRF_API_LOGGER_ENABLE_TRACING = settings.DRF_API_LOGGER_ENABLE_TRACING
            if self.DRF_API_LOGGER_ENABLE_TRACING and hasattr(settings, 'DRF_API_LOGGER_TRACING_ID_HEADER_NAME'):
                self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME = settings.DRF_API_LOGGER_TRACING_ID_HEADER_NAME

        self.tracing_func_name = None
        if hasattr(settings, 'DRF_API_LOGGER_TRACING_FUNC'):
            mod_name, func_name = settings.DRF_API_LOGGER_TRACING_FUNC.rsplit('.', 1)
            mod = importlib.import_module(mod_name)
            self.tracing_func_name = getattr(mod, func_name)

        self.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = DEFAULT_MAX_REQUEST_BODY_SIZE
        if hasattr(settings, 'DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE'):
            if type(settings.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE) is int:
                self.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = settings.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE

        self.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = DEFAULT_MAX_RESPONSE_BODY_SIZE
        if hasattr(settings, 'DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE'):
            if type(settings.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE) is int:
                self.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = settings.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE

        self.DRF_API_LOGGER_ENABLE_PROFILING = False
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_PROFILING'):
            self.DRF_API_LOGGER_ENABLE_PROFILING = settings.DRF_API_LOGGER_ENABLE_PROFILING

        self.DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
        if hasattr(settings, 'DRF_API_LOGGER_PROFILING_SQL_TRACKING'):
            self.DRF_API_LOGGER_PROFILING_SQL_TRACKING = settings.DRF_API_LOGGER_PROFILING_SQL_TRACKING

        self.DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 1.0
        if hasattr(settings, 'DRF_API_LOGGER_PROFILING_SAMPLE_RATE'):
            if type(settings.DRF_API_LOGGER_PROFILING_SAMPLE_RATE) in (int, float):
                sample_rate = float(settings.DRF_API_LOGGER_PROFILING_SAMPLE_RATE)
                self.DRF_API_LOGGER_PROFILING_SAMPLE_RATE = min(max(sample_rate, 0.0), 1.0)

        self.DRF_API_LOGGER_ENABLE_OTEL = False
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_OTEL'):
            self.DRF_API_LOGGER_ENABLE_OTEL = settings.DRF_API_LOGGER_ENABLE_OTEL

        self.DRF_API_LOGGER_ENABLE_METRICS = False
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_METRICS'):
            self.DRF_API_LOGGER_ENABLE_METRICS = settings.DRF_API_LOGGER_ENABLE_METRICS

        self.DRF_API_LOGGER_CONTENT_TYPES = self._build_content_types()

    def is_static_or_media_request(self, path):
        static_url = getattr(settings, 'STATIC_URL', None)
        media_url = getattr(settings, 'MEDIA_URL', None)

        # Check static URL
        if static_url and static_url != '/' and path.startswith(static_url):
            return True

        # Check media URL
        if media_url and media_url != '/' and path.startswith(media_url):
            return True

        return False

    def _extract_error_type(self, response_body, status_code):
        if isinstance(response_body, dict):
            detail = response_body.get('detail', '')
            if isinstance(detail, str) and detail:
                return detail[:256]
            code = response_body.get('code', '')
            if isinstance(code, str) and code:
                return code[:256]
        STATUS_MAP = {
            400: 'BadRequest',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'NotFound',
            405: 'MethodNotAllowed',
            408: 'RequestTimeout',
            429: 'Throttled',
            500: 'InternalServerError',
            502: 'BadGateway',
            503: 'ServiceUnavailable',
            504: 'GatewayTimeout',
        }
        return STATUS_MAP.get(status_code, 'HTTP{}'.format(status_code))

    def _build_content_types(self):
        content_types = {
            "application/json",
            "application/vnd.api+json",
            "application/gzip",
            "application/octet-stream",
            "text/calendar",
        }
        if hasattr(settings, "DRF_API_LOGGER_CONTENT_TYPES") and type(
            settings.DRF_API_LOGGER_CONTENT_TYPES
        ) in (list, tuple):
            for content_type in settings.DRF_API_LOGGER_CONTENT_TYPES:
                normalized = self._normalize_content_type(content_type)
                if normalized:
                    content_types.add(normalized)
        return content_types

    def _normalize_content_type(self, content_type):
        if not content_type:
            return ''
        return str(content_type).split(';', 1)[0].strip().lower()

    def _should_log_response_content_type(self, response):
        content_type = self._normalize_content_type(response.get("content-type"))
        return content_type in self.DRF_API_LOGGER_CONTENT_TYPES

    def _is_json_content_type(self, content_type):
        return content_type == 'application/json' or content_type.endswith('+json')

    def _truncation_marker(self, label, actual_size, limit):
        return '** {} truncated: {} bytes exceeds {} byte limit **'.format(
            label, actual_size, limit
        )

    def _decode_body(self, raw_body, limit, label, content_type):
        if not raw_body:
            return ''

        if isinstance(raw_body, str):
            raw_bytes = raw_body.encode('utf-8')
        else:
            raw_bytes = raw_body

        if limit > -1 and len(raw_bytes) > limit:
            return self._truncation_marker(label, len(raw_bytes), limit)

        try:
            decoded = raw_bytes.decode('utf-8')
        except Exception:
            return ''

        if self._is_json_content_type(content_type):
            try:
                return json.loads(decoded)
            except Exception:
                return ''

        try:
            return json.loads(decoded)
        except Exception:
            if content_type.startswith('text/') or content_type in (
                'application/xml',
                'application/x-www-form-urlencoded',
            ):
                return decoded
        return ''

    def _get_request_data(self, request):
        try:
            raw_body = request.body
        except Exception:
            return ''
        content_type = self._normalize_content_type(request.META.get('CONTENT_TYPE'))
        return self._decode_body(
            raw_body,
            self.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE,
            'Request body',
            content_type,
        )

    def _get_response_body(self, response):
        content_type = self._normalize_content_type(response.get("content-type"))
        if getattr(response, 'streaming', False):
            return '** Streaming **'
        if content_type == 'application/gzip':
            return '** GZIP Archive **'
        if content_type == 'application/octet-stream':
            return '** Binary File **'
        if content_type == 'text/calendar':
            return '** Calendar **'
        try:
            raw_body = response.content
        except Exception:
            return ''
        return self._decode_body(
            raw_body,
            self.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE,
            'Response body',
            content_type,
        )

    def _should_profile(self):
        if not self.DRF_API_LOGGER_ENABLE_PROFILING:
            return False
        if self.DRF_API_LOGGER_PROFILING_SAMPLE_RATE <= 0:
            return False
        if self.DRF_API_LOGGER_PROFILING_SAMPLE_RATE >= 1:
            return True
        return random.random() < self.DRF_API_LOGGER_PROFILING_SAMPLE_RATE

    def __call__(self, request):
        # Skip logging for static and media files
        if self.is_static_or_media_request(request.path):
            return self.get_response(request)

        # Run only if logger is enabled.
        if self.DRF_API_LOGGER_DATABASE or self.DRF_API_LOGGER_SIGNAL:

            try:
                resolver_match = resolve(request.path_info)
                url_name = resolver_match.url_name
                namespace = resolver_match.namespace
            except Exception:
                url_name = None
                namespace = None

            # Always skip Admin panel
            if namespace == 'admin':
                return self.get_response(request)

            # Skip for url name
            if url_name in self.DRF_API_LOGGER_SKIP_URL_NAME:
                return self.get_response(request)

            # Skip entire app using namespace
            if namespace in self.DRF_API_LOGGER_SKIP_NAMESPACE:
                return self.get_response(request)

            start_time = time.time()
            middleware_before_start = time.time()

            headers = get_headers(request=request)
            method = request.method

            request_data = self._get_request_data(request)

            tracing_id = None
            if self.DRF_API_LOGGER_ENABLE_TRACING:
                if self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME:
                    tracing_id = headers.get(self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME)
                if not tracing_id:
                    if self.tracing_func_name:
                        tracing_id = self.tracing_func_name()
                    else:
                        tracing_id = str(uuid.uuid4())
                request.tracing_id = tracing_id

            middleware_before_end = time.time()

            # Start OTel span before calling the view
            otel_span = None
            otel_span_owned = False
            if self.DRF_API_LOGGER_ENABLE_OTEL:
                from drf_api_logger.otel import start_span
                otel_span, otel_span_owned = start_span(method, request.path)

            # Set up SQL tracking before calling the view
            profile_this_request = self._should_profile()
            sql_profiling_active = (
                profile_this_request
                and self.DRF_API_LOGGER_PROFILING_SQL_TRACKING
            )
            sql_data = None
            if sql_profiling_active:
                from django.db import connection, reset_queries
                original_force_debug_cursor = connection.force_debug_cursor
                connection.force_debug_cursor = True
                reset_queries()

            view_start = time.time()
            caught_exception = None
            try:
                response = self.get_response(request)
            except Exception as e:
                caught_exception = e
                raise
            finally:
                view_end = time.time()
                if caught_exception:
                    request._drf_logger_error_type = type(caught_exception).__name__
                if sql_profiling_active:
                    queries = connection.queries[:]
                    sql_total_time = sum(float(q.get('time', 0)) for q in queries)
                    sql_query_count = len(queries)
                    sql_data = {
                        'total_time': round(sql_total_time, 5),
                        'query_count': sql_query_count,
                    }
                    connection.force_debug_cursor = original_force_debug_cursor
                    reset_queries()

            # Only log required status codes if matching
            if self.DRF_API_LOGGER_STATUS_CODES and response.status_code not in self.DRF_API_LOGGER_STATUS_CODES:
                return response

            # Log only registered methods if available.
            if len(self.DRF_API_LOGGER_METHODS) > 0 and method not in self.DRF_API_LOGGER_METHODS:
                return response

            if self._should_log_response_content_type(response):
                response_body = self._get_response_body(response)
                if self.DRF_API_LOGGER_PATH_TYPE == 'ABSOLUTE':
                    api = request.build_absolute_uri()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'FULL_PATH':
                    api = request.get_full_path()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'RAW_URI':
                    api = request.get_raw_uri()
                else:
                    api = request.build_absolute_uri()

                # Get the current time in a timezone-aware manner
                if settings.USE_TZ:
                    current_time = timezone.now()
                else:
                    current_time = datetime.now()

                middleware_after_start = time.time()

                data = dict(
                    api=mask_sensitive_data(api, mask_api_parameters=True),
                    headers=mask_sensitive_data(headers),
                    body=mask_sensitive_data(request_data),
                    method=method,
                    client_ip_address=get_client_ip(request),
                    response=mask_sensitive_data(response_body),
                    status_code=response.status_code,
                    execution_time=time.time() - start_time,
                    added_on=current_time
                )

                middleware_after_end = time.time()

                # Build profiling data if enabled
                profiling = None
                if profile_this_request:
                    profiling = {
                        'middleware_before_view': round(middleware_before_end - middleware_before_start, 5),
                        'view_and_serialization': round(view_end - view_start, 5),
                        'middleware_after_view': round(middleware_after_end - middleware_after_start, 5),
                    }
                    if sql_data:
                        profiling['sql'] = sql_data
                    data['profiling_data'] = profiling
                    data['sql_query_count'] = sql_data['query_count'] if sql_data else None

                # Capture error type for 4xx/5xx responses
                if response.status_code >= 400:
                    error_type = getattr(request, '_drf_logger_error_type', None)
                    if not error_type:
                        error_type = self._extract_error_type(response_body, response.status_code)
                    data['error_type'] = error_type

                if self.DRF_API_LOGGER_DATABASE and logger_apps.LOGGER_THREAD:
                    d = data.copy()
                    d.pop('error_type', None)
                    d['headers'] = json.dumps(d['headers'], indent=4, ensure_ascii=False) if d.get('headers') else ''
                    if request_data:
                        d['body'] = json.dumps(d['body'], indent=4, ensure_ascii=False) if d.get('body') else ''
                    d['response'] = json.dumps(d['response'], indent=4, ensure_ascii=False) if d.get('response') else ''
                    if d.get('profiling_data'):
                        d['profiling_data'] = json.dumps(d['profiling_data'], indent=4, ensure_ascii=False)
                    logger_apps.LOGGER_THREAD.put_log_data(data=d)
                if self.DRF_API_LOGGER_SIGNAL:
                    if tracing_id:
                        data.update({
                            'tracing_id': tracing_id
                        })
                    API_LOGGER_SIGNAL.listen(**data)
                if self.DRF_API_LOGGER_ENABLE_OTEL and otel_span:
                    from drf_api_logger.otel import finish_span
                    finish_span(otel_span, otel_span_owned, data, profiling)
                if self.DRF_API_LOGGER_ENABLE_METRICS:
                    from drf_api_logger.metrics import record_request
                    record_request(data)
            else:
                return response
        else:
            response = self.get_response(request)
        return response
