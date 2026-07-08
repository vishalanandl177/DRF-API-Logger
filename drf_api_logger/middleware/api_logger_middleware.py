import importlib
import hashlib
import hmac
import json
import random
import time
import uuid

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings
from django.urls import resolve
from django.utils import timezone
from datetime import datetime

from drf_api_logger import apps as logger_apps
from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.correlation import build_correlation_context, build_low_cardinality_metadata
from drf_api_logger.logging_context import clear_correlation_context, set_correlation_context
from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.labels import build_low_cardinality_from_resolver
from drf_api_logger.metrics.recorder import get_recorder
from drf_api_logger.metrics.security import (
    SecurityContext,
    evaluate_security_signals,
    sanitize_business_context,
)
from drf_api_logger.policy import safe_evaluate_logging_policy
from drf_api_logger.utils import get_headers, get_client_ip, mask_sensitive_data


DEFAULT_MAX_REQUEST_BODY_SIZE = 32768
DEFAULT_MAX_RESPONSE_BODY_SIZE = 65536


class APILoggerMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)
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

        self.DRF_API_LOGGER_ENABLE_CORRELATION = False
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_CORRELATION'):
            self.DRF_API_LOGGER_ENABLE_CORRELATION = settings.DRF_API_LOGGER_ENABLE_CORRELATION

        self.DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = ['X-Request-ID', 'X-Correlation-ID']
        if hasattr(settings, 'DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS'):
            if type(settings.DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS) in (list, tuple):
                self.DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = settings.DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS

        self.DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = ['traceparent', 'X-Trace-ID']
        if hasattr(settings, 'DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS'):
            if type(settings.DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS) in (list, tuple):
                self.DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = settings.DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS

        self.DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = False
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT'):
            self.DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = settings.DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT

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

    def _attach_correlation_context(self, request, correlation_context):
        low_cardinality = build_low_cardinality_metadata(correlation_context)
        request.api_logger_correlation = correlation_context.copy()
        request.api_logger_low_cardinality = low_cardinality.copy()

        request_id = correlation_context.get('request_id')
        trace_id = correlation_context.get('trace_id')
        if request_id:
            request.api_logger_request_id = request_id
        if trace_id:
            request.api_logger_trace_id = trace_id
            if not hasattr(request, 'tracing_id'):
                request.tracing_id = trace_id

        return low_cardinality

    def _policy_payload(self, decision, headers, request_data, response_body):
        return {
            'headers': headers if decision.headers else '',
            'request_data': request_data if decision.request_body else '',
            'response_body': response_body if decision.response_body else '',
        }

    def _policy_api(self, decision, request, api):
        if decision.policy_error:
            return getattr(request, 'path', '') or ''
        return api

    def _safe_queue_log_data(self, data):
        try:
            logger_apps.LOGGER_THREAD.put_log_data(data=data)
        except Exception:
            return False
        return True

    def _api_logger_storage_enabled(self):
        return self.DRF_API_LOGGER_DATABASE or self.DRF_API_LOGGER_SIGNAL

    def _api_logger_enabled(self):
        return (
            self._api_logger_storage_enabled()
            or metrics_settings.request_metrics_enabled()
            or metrics_settings.profiling_metrics_enabled()
        )

    def _resolve_request(self, request):
        try:
            resolver_match = resolve(request.path_info)
            return resolver_match, resolver_match.url_name, resolver_match.namespace
        except Exception:
            return None, None, None

    def _should_skip_resolved_request(self, url_name, namespace):
        if namespace == 'admin':
            return True
        if url_name in self.DRF_API_LOGGER_SKIP_URL_NAME:
            return True
        if namespace in self.DRF_API_LOGGER_SKIP_NAMESPACE:
            return True
        return False

    def _build_tracing_id(self, headers):
        if not self.DRF_API_LOGGER_ENABLE_TRACING:
            return None
        tracing_id = None
        if self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME:
            tracing_id = headers.get(self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME)
        if tracing_id:
            return tracing_id
        if self.tracing_func_name:
            return self.tracing_func_name()
        return str(uuid.uuid4())

    def _start_sql_profiling(self, profile_this_request):
        if not profile_this_request or not self.DRF_API_LOGGER_PROFILING_SQL_TRACKING:
            return None
        from django.db import connection, reset_queries
        original_force_debug_cursor = connection.force_debug_cursor
        connection.force_debug_cursor = True
        reset_queries()
        return connection, reset_queries, original_force_debug_cursor

    def _finish_sql_profiling(self, sql_profiling):
        if not sql_profiling:
            return None
        connection, reset_queries, original_force_debug_cursor = sql_profiling
        try:
            queries = connection.queries[:]
            sql_total_time = sum(float(query.get('time', 0)) for query in queries)
            sql_counts = {}
            for query in queries:
                sql = query.get('sql')
                if sql:
                    sql_counts[sql] = sql_counts.get(sql, 0) + 1
            duplicate_query_count = sum(count - 1 for count in sql_counts.values() if count > 1)
            return {
                'total_time': round(sql_total_time, 5),
                'query_count': len(queries),
                'duplicate_query_count': duplicate_query_count,
            }
        finally:
            connection.force_debug_cursor = original_force_debug_cursor
            reset_queries()

    def _get_request_body_sample(self, request):
        if not metrics_settings.security_metrics_enabled():
            return None
        if not metrics_settings.inspect_request_body_for_security():
            return None
        limit = metrics_settings.security_body_inspection_limit()
        if limit <= 0:
            return b""
        try:
            return request.body[:limit]
        except Exception:
            return None

    def _get_response_body_sample(self, response):
        if not metrics_settings.security_metrics_enabled():
            return None
        if not metrics_settings.inspect_response_body_for_security():
            return None
        if getattr(response, 'streaming', False):
            return None
        limit = metrics_settings.security_body_inspection_limit()
        if limit <= 0:
            return b""
        try:
            return response.content[:limit]
        except Exception:
            return None

    def _request_body_size_bytes(self, request):
        try:
            value = request.META.get('CONTENT_LENGTH')
            if value in (None, ''):
                return 0
            size = int(value)
            return size if size >= 0 else None
        except Exception:
            return None

    def _response_body_size_bytes(self, response):
        if getattr(response, 'streaming', False):
            return None
        try:
            value = response.get('content-length')
            if value not in (None, ''):
                size = int(value)
                return size if size >= 0 else None
        except Exception:
            pass
        try:
            return len(response.content)
        except Exception:
            return None

    def _is_slow_request(self, execution_time):
        threshold = metrics_settings.slow_request_threshold_seconds()
        if threshold is None:
            return False
        return execution_time >= threshold

    def _active_metric_labels(self, state):
        labels = state.get('metrics_low_cardinality', {}).copy()
        labels['method'] = state.get('method', 'unknown')
        return labels

    def _record_active_request_start(self, state):
        if not metrics_settings.api_metrics_enabled():
            return
        try:
            get_recorder().increment_active_requests(self._active_metric_labels(state))
            state['active_request_recorded'] = True
        except Exception:
            state['active_request_recorded'] = False

    def _record_active_request_end(self, state):
        if not state.get('active_request_recorded'):
            return
        try:
            get_recorder().decrement_active_requests(self._active_metric_labels(state))
        except Exception:
            pass
        finally:
            state['active_request_recorded'] = False

    def _record_exception_metrics(self, exception, state):
        if not metrics_settings.api_metrics_enabled():
            return
        labels = state.get('metrics_low_cardinality', {})
        event = {
            'method': state.get('method'),
            'status_code': 500,
            'exception_class': exception.__class__.__name__,
            'execution_time': time.time() - state['start_time'],
            'low_cardinality': labels.copy(),
        }
        try:
            get_recorder().increment_http_exception(event)
        except Exception:
            pass

    def _actor_fingerprint(self, request):
        if not metrics_settings.security_metrics_enabled():
            return None
        config = metrics_settings.security_actor_tracking_config()
        if not config.get('enabled', True):
            return None
        parts = []
        user = getattr(request, 'user', None)
        if config.get('include_user_id', True) and getattr(user, 'is_authenticated', False):
            user_id = getattr(user, 'pk', None)
            if user_id is not None:
                parts.append('user:{}'.format(user_id))
        if config.get('include_ip', True):
            ip = get_client_ip(request)
            if ip:
                parts.append('ip:{}'.format(ip))
        if config.get('include_user_agent_family', True):
            user_agent = str(request.META.get('HTTP_USER_AGENT', '')).split('/', 1)[0].strip()
            if user_agent:
                parts.append('ua:{}'.format(user_agent[:64]))
        if not parts:
            return None
        secret = str(getattr(settings, 'SECRET_KEY', 'drf-api-logger')).encode('utf-8')
        message = '|'.join(parts).encode('utf-8', errors='ignore')
        return hmac.new(secret, message, hashlib.sha256).hexdigest()[:32]

    def _business_context(self, request, response=None, exception=None):
        getter = metrics_settings.security_context_getter()
        if getter is None:
            return {}
        try:
            return sanitize_business_context(
                getter(request, response=response, exception=exception)
            )
        except Exception:
            return {}

    def _metrics_low_cardinality(self, state, response=None, status_code=None):
        low_cardinality = state.get('low_cardinality') or {}
        if status_code is None and response is not None:
            status_code = getattr(response, 'status_code', None)
        derived = build_low_cardinality_from_resolver(
            state.get('resolver_match'),
            status_code,
        )
        merged = derived.copy()
        for key, value in low_cardinality.items():
            if key == 'status_class' and value == metrics_settings.UNKNOWN_LABEL_VALUE:
                continue
            if key == 'route' and value == metrics_settings.UNKNOWN_LABEL_VALUE and derived.get('route'):
                continue
            if key == 'view_name' and value == metrics_settings.UNKNOWN_LABEL_VALUE and derived.get('view_name'):
                continue
            merged[key] = value
        if not merged.get('status_class') or merged.get('status_class') == metrics_settings.UNKNOWN_LABEL_VALUE:
            merged['status_class'] = derived.get('status_class', metrics_settings.UNKNOWN_LABEL_VALUE)
        return merged

    def _record_http_metrics(self, request, response, state):
        if not metrics_settings.api_metrics_enabled():
            return
        execution_time = time.time() - state['start_time']
        event = {
            'method': state['method'],
            'status_code': getattr(response, 'status_code', None),
            'execution_time': execution_time,
            'request_body_size_bytes': state.get('request_body_size_bytes'),
            'response_body_size_bytes': self._response_body_size_bytes(response),
            'is_slow': self._is_slow_request(execution_time),
            'throttle_scope': getattr(request, 'throttle_scope', 'unknown'),
            'low_cardinality': state.get('metrics_low_cardinality', {}),
        }
        try:
            get_recorder().observe_http_request(event)
        except Exception:
            return

    def _record_security_metrics(self, request, response, state, exception=None):
        if not metrics_settings.security_metrics_enabled():
            return
        labels = state.get('metrics_low_cardinality', {})
        detection_start = time.perf_counter()
        recorder = get_recorder()
        status_code = getattr(response, 'status_code', None) if response is not None else 500
        try:
            context = SecurityContext(
                request=request,
                response=response,
                exception=exception,
                route=labels.get('route', 'unknown'),
                method=state['method'],
                status_code=status_code,
                status_class=labels.get('status_class', 'unknown'),
                request_body_sample=state.get('request_body_sample'),
                response_body_sample=self._get_response_body_sample(response) if response is not None else None,
                actor_fingerprint=state.get('actor_fingerprint'),
                low_cardinality=labels.copy(),
                business_context=self._business_context(request, response=response, exception=exception),
            )
            def record_error(rule_id, exc):
                recorder.increment_security_detection_error(rule_id, exc.__class__.__name__)

            for signal in evaluate_security_signals(context, error_callback=record_error):
                recorder.observe_security_event(signal)
        except Exception as exc:
            try:
                recorder.increment_security_detection_error('unknown', exc.__class__.__name__)
            except Exception:
                return
        finally:
            try:
                recorder.observe_security_detection(
                    {'route': labels.get('route', 'unknown')},
                    time.perf_counter() - detection_start,
                )
            except Exception:
                return

    def _prepare_log_state(self, request):
        resolver_match, url_name, namespace = self._resolve_request(request)
        if self._should_skip_resolved_request(url_name, namespace):
            return None

        start_time = time.time()
        middleware_before_start = time.time()
        headers = get_headers(request=request)
        request_data = ''
        if self._api_logger_storage_enabled():
            payload_start = time.perf_counter()
            request_data = self._get_request_data(request)
            try:
                get_recorder().observe_payload_capture(
                    {'location': 'request'},
                    'request',
                    time.perf_counter() - payload_start,
                )
            except Exception:
                pass
        request_body_sample = self._get_request_body_sample(request)
        tracing_id = self._build_tracing_id(headers)
        if tracing_id:
            request.tracing_id = tracing_id
        middleware_before_end = time.time()

        correlation_context = {}
        low_cardinality = build_low_cardinality_from_resolver(resolver_match)
        logging_context_set = False
        if self.DRF_API_LOGGER_ENABLE_CORRELATION:
            correlation_context = build_correlation_context(
                request=request,
                headers=headers,
                resolver_match=resolver_match,
                tracing_id=tracing_id,
            )
            low_cardinality = self._attach_correlation_context(request, correlation_context)
            if self.DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT:
                set_correlation_context(correlation_context)
                logging_context_set = True

        profile_this_request = self._should_profile()

        return {
            'resolver_match': resolver_match,
            'start_time': start_time,
            'middleware_before_start': middleware_before_start,
            'middleware_before_end': middleware_before_end,
            'headers': headers,
            'method': request.method,
            'request_data': request_data,
            'request_body_sample': request_body_sample,
            'request_body_size_bytes': self._request_body_size_bytes(request),
            'actor_fingerprint': self._actor_fingerprint(request),
            'tracing_id': tracing_id,
            'correlation_context': correlation_context,
            'low_cardinality': low_cardinality,
            'metrics_low_cardinality': low_cardinality.copy(),
            'logging_context_set': logging_context_set,
            'profile_this_request': profile_this_request,
            'sql_profiling': self._start_sql_profiling(profile_this_request),
            'sql_data': None,
            'view_end': None,
            'active_request_recorded': False,
            'profiling_payload': None,
            'profiling_metrics_recorded': False,
        }

    def _finish_log_state_after_view(self, state, view_start):
        state['view_end'] = time.time()
        try:
            state['sql_data'] = self._finish_sql_profiling(state['sql_profiling'])
        finally:
            if state['logging_context_set']:
                clear_correlation_context()

    def _request_api(self, request):
        if self.DRF_API_LOGGER_PATH_TYPE == 'FULL_PATH':
            return request.get_full_path()
        if self.DRF_API_LOGGER_PATH_TYPE == 'RAW_URI':
            get_raw_uri = getattr(request, 'get_raw_uri', None)
            if get_raw_uri:
                return get_raw_uri()
            return request.build_absolute_uri(request.get_full_path())
        return request.build_absolute_uri()

    def _current_time(self):
        if settings.USE_TZ:
            return timezone.now()
        return datetime.now()

    def _build_log_data(self, request, response, state, policy_decision, policy_payload):
        masking_start = time.perf_counter()
        try:
            return dict(
                api=mask_sensitive_data(
                    self._policy_api(policy_decision, request, self._request_api(request)),
                    mask_api_parameters=True,
                    extra_sensitive_keys=policy_decision.mask_keys,
                ),
                headers=mask_sensitive_data(
                    policy_payload['headers'],
                    extra_sensitive_keys=policy_decision.mask_keys,
                ),
                body=mask_sensitive_data(
                    policy_payload['request_data'],
                    extra_sensitive_keys=policy_decision.mask_keys,
                ),
                method=state['method'],
                client_ip_address=get_client_ip(request),
                response=mask_sensitive_data(
                    policy_payload['response_body'],
                    extra_sensitive_keys=policy_decision.mask_keys,
                ),
                status_code=response.status_code,
                execution_time=time.time() - state['start_time'],
                added_on=self._current_time(),
            )
        finally:
            try:
                get_recorder().observe_masking(
                    {'location': 'log_event'},
                    'log_event',
                    time.perf_counter() - masking_start,
                )
            except Exception:
                pass

    def _build_profiling_payload(self, state, middleware_after_start):
        if not state['profile_this_request']:
            return None
        sql_data = state['sql_data']
        profiling = {
            'middleware_before_view': round(
                state['middleware_before_end'] - state['middleware_before_start'], 5
            ),
            'view_and_serialization': round(
                state['view_end'] - state['view_start'], 5
            ),
            'middleware_after_view': round(time.time() - middleware_after_start, 5),
        }
        if sql_data:
            profiling['sql'] = sql_data
        return profiling

    def _record_profiling_metrics(self, state, profiling):
        if not profiling or state.get('profiling_metrics_recorded'):
            return
        labels = state.get('metrics_low_cardinality', {}).copy()
        try:
            get_recorder().observe_profiling(labels, profiling)
            state['profiling_metrics_recorded'] = True
        except Exception:
            pass

    def _add_profiling_data(self, data, state, middleware_after_start):
        if not state['profile_this_request']:
            return
        profiling = state.get('profiling_payload')
        if profiling is None:
            profiling = self._build_profiling_payload(state, middleware_after_start)
            state['profiling_payload'] = profiling
            self._record_profiling_metrics(state, profiling)
        sql_data = state['sql_data']
        data['profiling_data'] = profiling
        data['sql_query_count'] = sql_data['query_count'] if sql_data else None

    def _database_payload(self, data, request_data):
        serialization_start = time.perf_counter()
        database_data = data.copy()
        try:
            database_data['headers'] = (
                json.dumps(database_data['headers'], indent=4, ensure_ascii=False)
                if database_data.get('headers') else ''
            )
            if request_data:
                database_data['body'] = (
                    json.dumps(database_data['body'], indent=4, ensure_ascii=False)
                    if database_data.get('body') else ''
                )
            database_data['response'] = (
                json.dumps(database_data['response'], indent=4, ensure_ascii=False)
                if database_data.get('response') else ''
            )
            if database_data.get('profiling_data'):
                database_data['profiling_data'] = json.dumps(
                    database_data['profiling_data'],
                    indent=4,
                    ensure_ascii=False,
                )
            return database_data
        finally:
            try:
                get_recorder().observe_serialization(
                    {'payload': 'database_log'},
                    time.perf_counter() - serialization_start,
                )
            except Exception:
                pass

    def _emit_log_data(self, data, state, policy_decision):
        if policy_decision.database and self.DRF_API_LOGGER_DATABASE and logger_apps.LOGGER_THREAD:
            self._safe_queue_log_data(
                self._database_payload(data, state['request_data'])
            )
        if policy_decision.signal and self.DRF_API_LOGGER_SIGNAL:
            signal_data = data.copy()
            if state['tracing_id']:
                signal_data.update({'tracing_id': state['tracing_id']})
            if state['correlation_context']:
                signal_data.update({
                    'correlation': state['correlation_context'].copy(),
                    'low_cardinality': state['low_cardinality'].copy(),
                })
            if getattr(settings, 'DRF_API_LOGGER_POLICY', None) or getattr(
                settings, 'DRF_API_LOGGER_POLICY_FUNC', None
            ):
                signal_data.update({'policy': policy_decision.to_signal_metadata()})
            API_LOGGER_SIGNAL.listen(**signal_data)

    def _finalize_log_response(self, request, response, state):
        try:
            logger_overhead_start = time.perf_counter()
            if self.DRF_API_LOGGER_ENABLE_CORRELATION:
                state['correlation_context'] = build_correlation_context(
                    request=request,
                    headers=state['headers'],
                    resolver_match=state['resolver_match'],
                    status_code=response.status_code,
                    tracing_id=state['tracing_id'],
                )
                state['low_cardinality'] = self._attach_correlation_context(
                    request,
                    state['correlation_context'],
                )

            state['metrics_low_cardinality'] = self._metrics_low_cardinality(state, response)
            self._record_http_metrics(request, response, state)
            self._record_security_metrics(request, response, state)

            middleware_after_start = time.time()
            if state['profile_this_request']:
                profiling = self._build_profiling_payload(state, middleware_after_start)
                state['profiling_payload'] = profiling
                self._record_profiling_metrics(state, profiling)

            if not self._api_logger_storage_enabled():
                return response

            if self.DRF_API_LOGGER_STATUS_CODES and response.status_code not in self.DRF_API_LOGGER_STATUS_CODES:
                return response
            if len(self.DRF_API_LOGGER_METHODS) > 0 and state['method'] not in self.DRF_API_LOGGER_METHODS:
                return response
            if not self._should_log_response_content_type(response):
                return response

            response_body = self._get_response_body(response)

            policy_decision = safe_evaluate_logging_policy(
                request=request,
                response=response,
                resolver_match=state['resolver_match'],
                correlation_context=state['correlation_context'],
                low_cardinality=state['low_cardinality'],
            )
            if not policy_decision.log:
                try:
                    get_recorder().increment_skipped_logs(policy_decision.reason)
                except Exception:
                    pass
                return response

            policy_payload = self._policy_payload(
                policy_decision,
                state['headers'],
                state['request_data'],
                response_body,
            )
            data = self._build_log_data(request, response, state, policy_decision, policy_payload)
            self._add_profiling_data(data, state, middleware_after_start)
            self._emit_log_data(data, state, policy_decision)
            try:
                get_recorder().observe_logger_overhead(
                    {
                        'route': state['metrics_low_cardinality'].get('route', 'unknown'),
                        'logging_enabled': 'true',
                    },
                    time.perf_counter() - logger_overhead_start,
                )
            except Exception:
                pass
            return response
        finally:
            self._record_active_request_end(state)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)
        if self.is_static_or_media_request(request.path):
            return self.get_response(request)
        if not self._api_logger_enabled():
            return self.get_response(request)

        state = self._prepare_log_state(request)
        if state is None:
            return self.get_response(request)

        self._record_active_request_start(state)
        state['view_start'] = time.time()
        try:
            response = self.get_response(request)
        except Exception as exc:
            self._finish_log_state_after_view(state, state['view_start'])
            state['metrics_low_cardinality'] = self._metrics_low_cardinality(state, status_code=500)
            self._record_exception_metrics(exc, state)
            self._record_security_metrics(request, None, state, exception=exc)
            self._record_active_request_end(state)
            raise
        self._finish_log_state_after_view(state, state['view_start'])
        return self._finalize_log_response(request, response, state)

    async def __acall__(self, request):
        if self.is_static_or_media_request(request.path):
            return await self.get_response(request)
        if not self._api_logger_enabled():
            return await self.get_response(request)

        state = self._prepare_log_state(request)
        if state is None:
            return await self.get_response(request)

        self._record_active_request_start(state)
        state['view_start'] = time.time()
        try:
            response = await self.get_response(request)
        except Exception as exc:
            self._finish_log_state_after_view(state, state['view_start'])
            state['metrics_low_cardinality'] = self._metrics_low_cardinality(state, status_code=500)
            self._record_exception_metrics(exc, state)
            self._record_security_metrics(request, None, state, exception=exc)
            self._record_active_request_end(state)
            raise
        self._finish_log_state_after_view(state, state['view_start'])
        return self._finalize_log_response(request, response, state)
