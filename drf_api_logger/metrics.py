from threading import Lock

_lock = Lock()

_counters = {
    'request_total': 0,
    'error_total': 0,
    'status_2xx': 0,
    'status_3xx': 0,
    'status_4xx': 0,
    'status_5xx': 0,
}

_latency_sum = 0.0
_latency_count = 0
_latency_max = 0.0

_per_method = {}
_per_endpoint = {}
_per_error_type = {}


def record_request(data):
    global _latency_sum, _latency_count, _latency_max

    status = data.get('status_code', 0)
    method = data.get('method', 'UNKNOWN')
    api = data.get('api', '')
    exec_time = data.get('execution_time', 0)
    error_type = data.get('error_type')

    with _lock:
        _counters['request_total'] += 1

        if 200 <= status < 300:
            _counters['status_2xx'] += 1
        elif 300 <= status < 400:
            _counters['status_3xx'] += 1
        elif 400 <= status < 500:
            _counters['status_4xx'] += 1
            _counters['error_total'] += 1
        elif status >= 500:
            _counters['status_5xx'] += 1
            _counters['error_total'] += 1

        _latency_sum += exec_time
        _latency_count += 1
        if exec_time > _latency_max:
            _latency_max = exec_time

        if method not in _per_method:
            _per_method[method] = 0
        _per_method[method] += 1

        endpoint_key = api.split('?')[0] if api else ''
        if endpoint_key not in _per_endpoint:
            _per_endpoint[endpoint_key] = {'count': 0, 'errors': 0, 'latency_sum': 0.0}
        _per_endpoint[endpoint_key]['count'] += 1
        _per_endpoint[endpoint_key]['latency_sum'] += exec_time
        if status >= 400:
            _per_endpoint[endpoint_key]['errors'] += 1

        if error_type:
            if error_type not in _per_error_type:
                _per_error_type[error_type] = 0
            _per_error_type[error_type] += 1


def get_metrics():
    with _lock:
        avg_latency = (_latency_sum / _latency_count) if _latency_count > 0 else 0
        error_rate = (
            (_counters['error_total'] / _counters['request_total']) * 100
        ) if _counters['request_total'] > 0 else 0

        return {
            'counters': dict(_counters),
            'latency': {
                'avg_ms': round(avg_latency * 1000, 3),
                'max_ms': round(_latency_max * 1000, 3),
                'total_requests': _latency_count,
            },
            'per_method': dict(_per_method),
            'per_endpoint': dict(_per_endpoint),
            'per_error_type': dict(_per_error_type),
            'error_rate_pct': round(error_rate, 2),
        }


def format_prometheus():
    m = get_metrics()
    lines = []
    lines.append('# HELP drf_api_logger_requests_total Total API requests')
    lines.append('# TYPE drf_api_logger_requests_total counter')
    lines.append('drf_api_logger_requests_total {}'.format(m['counters']['request_total']))

    lines.append('# HELP drf_api_logger_errors_total Total API errors (4xx + 5xx)')
    lines.append('# TYPE drf_api_logger_errors_total counter')
    lines.append('drf_api_logger_errors_total {}'.format(m['counters']['error_total']))

    lines.append('# HELP drf_api_logger_error_rate_pct Error rate percentage')
    lines.append('# TYPE drf_api_logger_error_rate_pct gauge')
    lines.append('drf_api_logger_error_rate_pct {}'.format(m['error_rate_pct']))

    for status_key in ['status_2xx', 'status_3xx', 'status_4xx', 'status_5xx']:
        code_range = status_key.replace('status_', '')
        lines.append('drf_api_logger_responses_total{{range="{}"}} {}'.format(
            code_range, m['counters'][status_key]
        ))

    lines.append('# HELP drf_api_logger_latency_avg_ms Average request latency in milliseconds')
    lines.append('# TYPE drf_api_logger_latency_avg_ms gauge')
    lines.append('drf_api_logger_latency_avg_ms {}'.format(m['latency']['avg_ms']))

    lines.append('# HELP drf_api_logger_latency_max_ms Maximum request latency in milliseconds')
    lines.append('# TYPE drf_api_logger_latency_max_ms gauge')
    lines.append('drf_api_logger_latency_max_ms {}'.format(m['latency']['max_ms']))

    for method, count in m['per_method'].items():
        lines.append('drf_api_logger_requests_by_method{{method="{}"}} {}'.format(method, count))

    for error_type, count in m['per_error_type'].items():
        safe_type = error_type.replace('"', '\\"')
        lines.append('drf_api_logger_errors_by_type{{type="{}"}} {}'.format(safe_type, count))

    for endpoint, stats in sorted(m['per_endpoint'].items(), key=lambda x: -x[1]['count'])[:50]:
        safe_ep = endpoint.replace('"', '\\"')
        avg_ms = round((stats['latency_sum'] / stats['count']) * 1000, 3) if stats['count'] > 0 else 0
        lines.append('drf_api_logger_endpoint_requests{{endpoint="{}"}} {}'.format(safe_ep, stats['count']))
        lines.append('drf_api_logger_endpoint_errors{{endpoint="{}"}} {}'.format(safe_ep, stats['errors']))
        lines.append('drf_api_logger_endpoint_latency_avg_ms{{endpoint="{}"}} {}'.format(safe_ep, avg_ms))

    return '\n'.join(lines) + '\n'


def reset_metrics():
    global _latency_sum, _latency_count, _latency_max
    with _lock:
        for key in _counters:
            _counters[key] = 0
        _latency_sum = 0.0
        _latency_count = 0
        _latency_max = 0.0
        _per_method.clear()
        _per_endpoint.clear()
        _per_error_type.clear()
