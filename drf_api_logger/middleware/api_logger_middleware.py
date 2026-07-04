import importlib
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

    def _api_logger_enabled(self):
        return self.DRF_API_LOGGER_DATABASE or self.DRF_API_LOGGER_SIGNAL

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
            return {
                'total_time': round(sql_total_time, 5),
                'query_count': len(queries),
            }
        finally:
            connection.force_debug_cursor = original_force_debug_cursor
            reset_queries()

    def _prepare_log_state(self, request):
        resolver_match, url_name, namespace = self._resolve_request(request)
        if self._should_skip_resolved_request(url_name, namespace):
            return None

        start_time = time.time()
        middleware_before_start = time.time()
        headers = get_headers(request=request)
        request_data = self._get_request_data(request)
        tracing_id = self._build_tracing_id(headers)
        if tracing_id:
            request.tracing_id = tracing_id
        middleware_before_end = time.time()

        correlation_context = {}
        low_cardinality = {}
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
            'tracing_id': tracing_id,
            'correlation_context': correlation_context,
            'low_cardinality': low_cardinality,
            'logging_context_set': logging_context_set,
            'profile_this_request': profile_this_request,
            'sql_profiling': self._start_sql_profiling(profile_this_request),
            'sql_data': None,
            'view_end': None,
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

    def _add_profiling_data(self, data, state, middleware_after_start):
        if not state['profile_this_request']:
            return
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
        data['profiling_data'] = profiling
        data['sql_query_count'] = sql_data['query_count'] if sql_data else None

    def _database_payload(self, data, request_data):
        database_data = data.copy()
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
        if self.DRF_API_LOGGER_STATUS_CODES and response.status_code not in self.DRF_API_LOGGER_STATUS_CODES:
            return response
        if len(self.DRF_API_LOGGER_METHODS) > 0 and state['method'] not in self.DRF_API_LOGGER_METHODS:
            return response
        if not self._should_log_response_content_type(response):
            return response

        response_body = self._get_response_body(response)
        middleware_after_start = time.time()

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

        policy_decision = safe_evaluate_logging_policy(
            request=request,
            response=response,
            resolver_match=state['resolver_match'],
            correlation_context=state['correlation_context'],
            low_cardinality=state['low_cardinality'],
        )
        if not policy_decision.log:
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
        return response

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

        state['view_start'] = time.time()
        try:
            response = self.get_response(request)
        finally:
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

        state['view_start'] = time.time()
        try:
            response = await self.get_response(request)
        finally:
            self._finish_log_state_after_view(state, state['view_start'])
        return self._finalize_log_response(request, response, state)
