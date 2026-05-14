"""
Production Setup — Optimized for real-world deployments.

Add these settings to your Django settings.py for a production environment.
"""

# --- Core ---
DRF_API_LOGGER_DATABASE = True

# --- Performance: tune queue for your traffic ---
DRF_LOGGER_QUEUE_MAX_SIZE = 100   # Batch size before bulk insert (default: 50)
DRF_LOGGER_INTERVAL = 5          # Flush interval in seconds (default: 10)

# --- Security: mask sensitive fields ---
DRF_API_LOGGER_EXCLUDE_KEYS = [
    'password', 'token', 'access', 'refresh',
    'secret', 'api_key', 'credit_card', 'ssn',
    'authorization',
]

# --- Profiling: identify bottlenecks without profiling every request ---
DRF_API_LOGGER_ENABLE_PROFILING = True
DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.1

# --- Slow API detection ---
DRF_API_LOGGER_SLOW_API_ABOVE = 500  # Flag APIs slower than 500ms

# --- Skip noisy endpoints ---
DRF_API_LOGGER_SKIP_URL_NAME = ['health-check', 'readiness', 'metrics']

# --- Payload limits: prevent logging huge uploads ---
DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768    # Default: 32 KB
DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536   # Default: 64 KB

# For regulated endpoints, set either limit to 0 to store truncation markers
# instead of body content.

# --- Request tracing ---
DRF_API_LOGGER_ENABLE_TRACING = True
DRF_API_LOGGER_TRACING_ID_HEADER_NAME = 'X-Request-ID'

# --- OpenTelemetry (requires: pip install drf-api-logger[otel]) ---
# DRF_API_LOGGER_ENABLE_OTEL = True

# --- Use a dedicated database for logs (recommended) ---
# DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'
# DATABASES['logs_db'] = {
#     'ENGINE': 'django.db.backends.postgresql',
#     'NAME': 'api_logs',
#     'HOST': 'logs-db.internal',
# }

# --- Timezone: display logs in your local timezone ---
# DRF_API_LOGGER_TIMEDELTA = 330   # IST (UTC+5:30)
# DRF_API_LOGGER_TIMEDELTA = -300  # EST (UTC-5:00)
