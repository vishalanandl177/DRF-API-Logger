import re

from django.conf import settings
from django.utils.module_loading import import_string


SAFE_CORRELATION_ID_RE = re.compile(r'^[A-Za-z0-9._:/=@+-]{1,128}$')
TRACEPARENT_RE = re.compile(
    r'^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}(?:-.+)?$',
    re.IGNORECASE,
)
CONTROL_CHAR_RE = re.compile(r'[\x00-\x1f\x7f]')

DEFAULT_REQUEST_ID_HEADERS = ['X-Request-ID', 'X-Correlation-ID']
DEFAULT_TRACE_ID_HEADERS = ['traceparent', 'X-Trace-ID']
OPAQUE_CONTEXT_KEYS = ('actor_id', 'tenant_id', 'api_consumer_id', 'client_id')
LOW_CARDINALITY_KEYS = (
    'route',
    'view_name',
    'app_name',
    'namespace',
    'url_name',
    'status_class',
)


def _configured_list(name, default):
    value = getattr(settings, name, default)
    if type(value) in (list, tuple):
        return value
    return default


def _normalize_header_name(name):
    normalized = str(name).strip().upper().replace('-', '_')
    if normalized.startswith('HTTP_'):
        normalized = normalized[5:]
    return normalized


def get_header_value(headers, header_names):
    normalized_headers = {
        _normalize_header_name(name): value
        for name, value in headers.items()
    }
    for header_name in header_names:
        value = normalized_headers.get(_normalize_header_name(header_name))
        if value:
            return value
    return None


def sanitize_correlation_id(value):
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None
    if not SAFE_CORRELATION_ID_RE.match(value):
        return None
    return value


def _safe_metadata_value(value, max_length=256):
    if value is None:
        return None

    value = str(value).strip()
    if not value or len(value) > max_length:
        return None
    if CONTROL_CHAR_RE.search(value):
        return None
    return value


def parse_traceparent(value):
    if value is None:
        return None

    match = TRACEPARENT_RE.match(str(value).strip())
    if not match:
        return None

    trace_id, parent_id = match.groups()
    if trace_id == '0' * 32 or parent_id == '0' * 16:
        return None
    return trace_id.lower()


def _get_trace_id(headers, tracing_id):
    for header_name in _configured_list(
        'DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS',
        DEFAULT_TRACE_ID_HEADERS,
    ):
        value = get_header_value(headers, [header_name])
        if not value:
            continue

        if _normalize_header_name(header_name) == 'TRACEPARENT':
            trace_id = parse_traceparent(value)
        else:
            trace_id = sanitize_correlation_id(value)

        if trace_id:
            return trace_id

    return sanitize_correlation_id(tracing_id)


def _get_view_name(resolver_match):
    if not resolver_match:
        return None

    view_func = getattr(resolver_match, 'func', None)
    view_class = getattr(view_func, 'view_class', None)
    if view_class:
        return '{}.{}'.format(view_class.__module__, view_class.__name__)
    if view_func:
        return '{}.{}'.format(view_func.__module__, view_func.__name__)
    return None


def _status_class(status_code):
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        return None
    if status_code < 100 or status_code > 599:
        return None
    return '{}xx'.format(status_code // 100)


def _opaque_context_from_request(request):
    context_func = getattr(settings, 'DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC', None)
    if not context_func:
        return {}

    try:
        context = import_string(context_func)(request)
    except Exception:
        return {}
    if type(context) is not dict:
        return {}

    return {
        key: sanitize_correlation_id(context.get(key))
        for key in OPAQUE_CONTEXT_KEYS
        if sanitize_correlation_id(context.get(key))
    }


def build_correlation_context(request, headers, resolver_match=None, status_code=None, tracing_id=None):
    if not getattr(settings, 'DRF_API_LOGGER_ENABLE_CORRELATION', False):
        return {}

    context = {}

    request_id = sanitize_correlation_id(
        get_header_value(
            headers,
            _configured_list(
                'DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS',
                DEFAULT_REQUEST_ID_HEADERS,
            ),
        )
    )
    trace_id = _get_trace_id(headers, tracing_id)

    if request_id:
        context['request_id'] = request_id
    if trace_id:
        context['trace_id'] = trace_id

    if resolver_match:
        route = _safe_metadata_value(getattr(resolver_match, 'route', None))
        app_name = _safe_metadata_value(getattr(resolver_match, 'app_name', None))
        namespace = _safe_metadata_value(getattr(resolver_match, 'namespace', None))
        url_name = _safe_metadata_value(getattr(resolver_match, 'url_name', None))
        view_name = _safe_metadata_value(_get_view_name(resolver_match))

        for key, value in (
            ('route', route),
            ('view_name', view_name),
            ('app_name', app_name),
            ('namespace', namespace),
            ('url_name', url_name),
        ):
            if value:
                context[key] = value

    status_bucket = _status_class(status_code)
    if status_bucket:
        context['status_class'] = status_bucket

    context.update(_opaque_context_from_request(request))
    return context


def build_low_cardinality_metadata(correlation_context):
    return {
        key: value
        for key, value in correlation_context.items()
        if key in LOW_CARDINALITY_KEYS and value
    }
