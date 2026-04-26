try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode, SpanKind
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


_tracer = None


def get_tracer():
    global _tracer
    if _tracer is None and HAS_OTEL:
        _tracer = trace.get_tracer('drf_api_logger', '1.2.0')
    return _tracer


def start_span(method, path):
    if not HAS_OTEL:
        return None, None
    tracer = get_tracer()
    if tracer is None:
        return None, None
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        return current_span, False
    span = tracer.start_span(
        '{} {}'.format(method, path),
        kind=SpanKind.SERVER,
    )
    return span, True


def finish_span(span, is_owned, data, profiling=None):
    if not HAS_OTEL or span is None:
        return
    _set_attributes(span, data, profiling)
    if is_owned:
        span.end()


def _set_attributes(span, data, profiling=None):
    if not span.is_recording():
        return
    span.set_attribute('http.method', data.get('method', ''))
    span.set_attribute('http.url', str(data.get('api', '')))
    span.set_attribute('http.status_code', data.get('status_code', 0))
    span.set_attribute('http.client_ip', data.get('client_ip_address', ''))
    span.set_attribute('drf.execution_time_ms', round(data.get('execution_time', 0) * 1000, 3))

    status_code = data.get('status_code', 0)
    if status_code >= 500:
        span.set_status(StatusCode.ERROR, 'HTTP {}'.format(status_code))
    elif status_code >= 400:
        span.set_status(StatusCode.ERROR, 'HTTP {}'.format(status_code))
    else:
        span.set_status(StatusCode.OK)

    if profiling:
        span.set_attribute(
            'drf.profiling.middleware_before_view_ms',
            round(profiling.get('middleware_before_view', 0) * 1000, 3)
        )
        span.set_attribute(
            'drf.profiling.view_and_serialization_ms',
            round(profiling.get('view_and_serialization', 0) * 1000, 3)
        )
        span.set_attribute(
            'drf.profiling.middleware_after_view_ms',
            round(profiling.get('middleware_after_view', 0) * 1000, 3)
        )
        sql = profiling.get('sql')
        if sql:
            span.set_attribute('db.query_count', sql.get('query_count', 0))
            span.set_attribute('db.total_time_ms', round(sql.get('total_time', 0) * 1000, 3))
