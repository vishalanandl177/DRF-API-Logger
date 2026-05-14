"""
High-Traffic Setup — For APIs handling 10K+ requests/minute.

Tuned for minimum overhead and maximum throughput.
"""

# --- Core ---
DRF_API_LOGGER_DATABASE = True

# --- Dedicated log database to avoid contention on your main DB ---
DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'myapp',
    },
    'logs_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'api_logs',
        'HOST': 'logs-replica.internal',
    },
}

# --- Aggressive batching: fewer DB round-trips ---
DRF_LOGGER_QUEUE_MAX_SIZE = 500  # Wake worker around 500 queued entries
DRF_LOGGER_INTERVAL = 3          # Or every 3 seconds, whichever comes first

# --- Reduce payload size: don't store large bodies ---
DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 4096     # 4 KB max
DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 8192    # 8 KB max

# --- Only log what matters ---
DRF_API_LOGGER_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
DRF_API_LOGGER_SKIP_URL_NAME = [
    'health-check', 'readiness', 'liveness', 'metrics', 'favicon',
]
DRF_API_LOGGER_SKIP_NAMESPACE = ['monitoring', 'internal']

# --- Profiling: enable selectively ---
DRF_API_LOGGER_ENABLE_PROFILING = True
DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.05

# --- Slow API detection ---
DRF_API_LOGGER_SLOW_API_ABOVE = 200  # 200ms threshold

# --- Security ---
DRF_API_LOGGER_EXCLUDE_KEYS = [
    'password', 'token', 'access', 'refresh', 'secret',
    'api_key', 'authorization', 'cookie', 'session',
]

# --- Tracing: propagate from load balancer ---
DRF_API_LOGGER_ENABLE_TRACING = True
DRF_API_LOGGER_TRACING_ID_HEADER_NAME = 'X-Request-ID'

# --- OpenTelemetry: export to your APM ---
# DRF_API_LOGGER_ENABLE_OTEL = True

# --- Periodic cleanup: add to your cron/celery beat ---
# from drf_api_logger.models import APILogsModel
# from django.utils import timezone
# from datetime import timedelta
#
# def cleanup_old_logs():
#     cutoff = timezone.now() - timedelta(days=7)
#     deleted, _ = APILogsModel.objects.using('logs_db').filter(
#         added_on__lt=cutoff
#     ).delete()
#     print(f"Deleted {deleted} old log entries")

# --- Recommended database indexes (run once via migration or SQL) ---
# CREATE INDEX idx_api_logs_added_on ON drf_api_logs(added_on);
# CREATE INDEX idx_api_logs_api_method ON drf_api_logs(api, method);
# CREATE INDEX idx_api_logs_status ON drf_api_logs(status_code, added_on);
# CREATE INDEX idx_api_logs_sql_count ON drf_api_logs(sql_query_count)
#     WHERE sql_query_count IS NOT NULL;
