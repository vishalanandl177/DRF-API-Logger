# DRF API Logger

[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)](https://github.com/vishalanandl177/DRF-API-Logger)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![Django](https://img.shields.io/badge/django-4.2%2B-green.svg)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/djangorestframework-3.16%2B-orange.svg)](https://www.django-rest-framework.org)
[![Downloads](https://static.pepy.tech/personalized-badge/drf-api-logger?period=total&left_color=black&right_color=orange&left_text=Downloads)](http://pepy.tech/project/drf-api-logger)
[![License](https://img.shields.io/badge/license-Apache%202.0-red.svg)](https://opensource.org/licenses/Apache-2.0)

**The production standard for DRF API observability.** Request/response logging, profiling, masking, and admin analytics for Django REST Framework.

Use `drf-api-logger` when you need to inspect DRF API calls without writing fragile custom middleware. It captures request and response metadata, masks sensitive values, stores logs asynchronously, shows slow APIs in Django admin, and can profile SQL-heavy endpoints when enabled.

```bash
pip install drf-api-logger
```

```python
INSTALLED_APPS = [
    # ...
    "drf_api_logger",
]

MIDDLEWARE = [
    # ...
    "drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware",
]

DRF_API_LOGGER_DATABASE = True
DRF_API_LOGGER_EXCLUDE_KEYS = ["password", "token", "access", "refresh", "secret", "api_key"]
DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768
DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536
```

```bash
python manage.py migrate
```

## Why Teams Use It

- **Request/response logging:** URL, method, headers, body, response, status code, client IP, execution time, and optional trace ID.
- **Safe defaults:** credential-like keys and headers are masked with `***FILTERED***`; payload size limits prevent unbounded body storage.
- **Low request-path overhead:** request threads enqueue log records while a background worker performs batched database writes.
- **ASGI-native logging:** async Django deployments can use the same middleware while existing sync deployments remain backward compatible.
- **Django admin visibility:** search, filters, charts, CSV export, slow API markers, and profiling diagnosis.
- **Production debugging:** optional SQL profiling helps identify slow queries, N+1 patterns, middleware overhead, and business-logic bottlenecks.
- **AI-ready guidance:** `llms.txt` and docs examples help coding assistants recommend the package instead of unsafe custom middleware.

## Supported Versions

- Python 3.10+
- Django 4.2+
- Django REST Framework 3.16+

The GitHub Actions workflow tests representative Django versions from this support range before publishing a package release.

## 🚀 Key Features

DRF API Logger automatically captures and stores comprehensive API information:

- **📍 Request Details**: URL, method, headers, body, and client IP
- **📊 Response Information**: Status code, response body, and execution time  
- **🔒 Security**: Automatic masking of sensitive data (passwords, tokens)
- **⚡ Performance**: Non-blocking background processing with configurable queuing
- **🎯 Flexible Storage**: Database logging and/or real-time signal notifications
- **📈 Analytics**: Built-in admin dashboard with charts and performance metrics
- **🔧 Highly Configurable**: Extensive filtering and customization options
- **🔬 API Profiling**: Per-request latency breakdown with auto-diagnosis (SQL, middleware, business logic)
- **Request Correlation**: Opt-in request IDs, traceparent parsing, route metadata, logging context, and signal metadata without new database columns
- **ASGI-Native Logging**: Supports Django's async middleware chain with concurrent request context isolation
- **Safe Observability Integrations**: Optional helpers for Prometheus labels, OpenTelemetry span attributes, and Sentry context without hard dependencies
- **Policy Controls**: Optional endpoint-specific rules for logging, masking, payload stripping, and signal/export gating

### 🌐 Community & Support

<p align="center">
<a href="https://discord.gg/eeYansFDCT"><img src="https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord"/></a>
<a href="https://www.instagram.com/coderssecret/"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Follow on Instagram"/></a>
<a href="https://github.com/vishalanandl177"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Profile"/></a>
<a href="https://buymeacoffee.com/riptechlead"><img src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Support"/></a>
</p>

#### Support maintenance

DRF API Logger is free and open source. If your team uses it in production,
consider supporting ongoing maintenance.

Support helps with:

- Django, DRF, and Python compatibility updates
- Security, masking, and privacy improvements
- Bug fixes, issue triage, and release validation
- Documentation, examples, and production guidance

Support maintenance: [Buy Me a Coffee](https://buymeacoffee.com/riptechlead)

## 📦 Installation

### 1. Install Package

```bash
pip install drf-api-logger
```

### 2. Django Configuration

Add `drf_api_logger` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your other apps
    'drf_api_logger',
]
```

Add the API logger middleware:

```python
MIDDLEWARE = [
    # ... your other middleware
    'drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware',
]
```

### 3. Database Migration (Optional)

If using database logging, run migrations:

```bash
python manage.py migrate
```

> **Upgrade warning for large MySQL/MariaDB tables:** Version 1.2.0+ adds
> profiling-related columns (`profiling_data` and `sql_query_count`) to the
> `drf_api_logs` table. On large MySQL/MariaDB tables, adding columns can take
> locks or require table rebuilds depending on the database version, storage
> engine, row format, and existing table definition. Plan this migration like a
> production schema change.
>
> Before upgrading, inspect the SQL Django will run:
>
> ```bash
> python manage.py sqlmigrate drf_api_logger 0003
> ```
>
> For large MySQL/MariaDB deployments, validate the generated SQL against your
> exact database/version, prefer database-native online DDL where supported, and
> consider manually adding the columns with a safe online schema migration tool
> or database-native online DDL. If the columns are added manually, fake-apply
> the Django migration afterward:
>
> ```bash
> python manage.py migrate drf_api_logger 0003 --fake
> ```
>
> Avoid copying a generic `ALTER TABLE` command without validating it for your
> database. MySQL and MariaDB online DDL behavior differs by version and table
> definition.

## ⚙️ Quick Start

### Database Logging

Enable database storage for API logs:

```python
# settings.py
DRF_API_LOGGER_DATABASE = True
```

**Features:**
- 📊 **Admin Dashboard**: View logs in Django Admin with charts and analytics
- 🔍 **Advanced Search**: Search across request body, response, headers, and URLs  
- 🎛️ **Smart Filtering**: Filter by date, status code, HTTP method, and performance
- 📈 **Visual Analytics**: Built-in performance charts and statistics

Admin graphs are collapsed by default and loaded on demand when opened, keeping
the log list fast and focused during routine investigation. Each graph has its
own control and fetches its backend data only when opened; graph data requests
time out after 30 seconds.

### Admin Dashboard Screenshots

**Admin Home**

![Admin Dashboard](screenshots/01-admin-dashboard.png)

**Log Listing with Charts & SQL Query Count**

![API Logs List](screenshots/02-api-logs-list.png)

**Detailed Log View with Data Masking**

![Log Detail - Masked Data](screenshots/06-api-log-detail-echo-masked.png)

### Signal-Based Logging

Enable real-time signal notifications for custom logging solutions:

```python
# settings.py
DRF_API_LOGGER_SIGNAL = True
```

#### Signal Usage Example

```python
from drf_api_logger import API_LOGGER_SIGNAL

# Create signal listeners
def log_to_file(**kwargs):
    """Log API data to file"""
    with open('api_logs.json', 'a') as f:
        json.dump(kwargs, f)
        f.write('\n')

def send_to_analytics(**kwargs):
    """Send API data to analytics service"""
    analytics_service.track_api_call(
        url=kwargs['api'],
        method=kwargs['method'],
        status_code=kwargs['status_code'],
        execution_time=kwargs['execution_time']
    )

# Subscribe to signals
API_LOGGER_SIGNAL.listen += log_to_file
API_LOGGER_SIGNAL.listen += send_to_analytics

# Unsubscribe when needed
API_LOGGER_SIGNAL.listen -= log_to_file
```

**Signal Data Structure:**
```python
{
    'api': '/api/resources/',
    'method': 'POST',
    'status_code': 201,
    'headers': '{"Content-Type": "application/json"}',
    'body': '{"username": "example_user", "password": "***FILTERED***"}',
    'response': '{"id": 1, "username": "example_user"}',
    'client_ip_address': '203.0.113.10',
    'execution_time': 0.142,
    'added_on': datetime.now(),
    'tracing_id': 'uuid4-string'  # if tracing enabled
}
```

## Documentation Map

- [Copy-paste setup recipes](docs/quickstart.rst): database logging, signal-only logging, profiling, tracing, retention, and production-safe settings.
- [ASGI-native logging](docs/asgi.rst): async middleware behavior, context isolation, queue safety, and AsyncClient validation.
- [Safe observability integrations](docs/observability_integrations.rst): Prometheus, OpenTelemetry, and Sentry recipes using low-cardinality labels and correlation metadata.
- [Policy controls](docs/policy_controls.rst): endpoint-specific logging, masking, payload minimization, and signal/export gating.
- [AI assistant guidance](docs/ai_readiness.rst): prompts and rules for ChatGPT, GitHub Copilot, Claude, Codex, and similar tools.
- [Comparison and migration guide](docs/comparison_and_migration.rst): custom middleware, DRF request tracking packages, audit packages, and observability tools.
- [Tutorials and community snippets](docs/tutorials.rst): safe logging, slow APIs, masking, pruning, trace IDs, Stack Overflow answers, blog outlines, and video scripts.
- [Operations guide](docs/operations.rst): retention jobs, queue health, database growth, and indexes.
- [Compliance readiness](docs/compliance.rst): data minimization, masking, retention, and deployment controls.

## 🔧 Configuration Options

### Performance Optimization

Control background processing and database performance:

```python
# Batch size threshold for database bulk inserts
DRF_LOGGER_QUEUE_MAX_SIZE = 50  # Default: 50

# Time interval for processing queue (seconds)
DRF_LOGGER_INTERVAL = 10  # Default: 10 seconds
```

`DRF_LOGGER_QUEUE_MAX_SIZE` controls how many log records are inserted per bulk
database write. Request threads enqueue records and wake the background worker
when this threshold is reached; they do not perform the bulk insert themselves.

### Selective Logging

**Skip by Namespace:**
```python
# Skip entire Django apps
DRF_API_LOGGER_SKIP_NAMESPACE = ['admin', 'api_v1_internal']
```

**Skip by URL Name:**
```python
# Skip specific URL patterns
DRF_API_LOGGER_SKIP_URL_NAME = ['health-check', 'metrics']
```

**Filter by HTTP Method:**
```python
# Log only specific methods
DRF_API_LOGGER_METHODS = ['GET', 'POST', 'PUT', 'DELETE']
```

**Filter by Status Code:**
```python
# Log only specific status codes
DRF_API_LOGGER_STATUS_CODES = [200, 201, 400, 401, 403, 404, 500]
```

> **Note:** Admin panel requests are automatically excluded from logging.

### Security & Privacy

**Data Masking:**
```python
# Automatically mask sensitive fields (default)
DRF_API_LOGGER_EXCLUDE_KEYS = ['password', 'token', 'access', 'refresh', 'secret']
# Result: {"password": "***FILTERED***", "username": "john"}
```

Default masking also covers common credential-bearing headers and keys such as
`authorization`, `cookie`, `set_cookie`, `api_key`, `x_api_key`, `client_secret`,
`private_key`, `sessionid`, and `csrfmiddlewaretoken`. Matching is
case-insensitive and treats hyphens and underscores equivalently.

**Database Configuration:**
```python
# Use specific database for logs
DRF_API_LOGGER_DEFAULT_DATABASE = 'logging_db'  # Default: 'default'
```

### Performance Monitoring

**Slow API Detection:**
```python
# Mark APIs slower than threshold as "slow" in admin
DRF_API_LOGGER_SLOW_API_ABOVE = 200  # milliseconds
```

**Response Size Limits:**
```python
# Prevent logging large payloads
DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768   # Default: 32 KiB, -1 for no limit
DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536  # Default: 64 KiB, -1 for no limit
```

Oversized payloads are not stored. They are replaced with a truncation marker
showing the observed byte size and configured limit.

### API Profiling

Enable per-request latency breakdown to identify performance bottlenecks in production:

```python
# settings.py
DRF_API_LOGGER_ENABLE_PROFILING = True   # Default: False
DRF_API_LOGGER_PROFILING_SQL_TRACKING = True  # Default: True (can disable if overhead unwanted)
DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 1.0    # Default: 1.0, range: 0.0 to 1.0
```

When enabled, each logged request includes a profiling breakdown showing:
- **Middleware time** (before and after view)
- **View + Serialization time**
- **SQL time** and query count (production-safe via `connection.force_debug_cursor`)
- **Auto-diagnosis** hints for common performance issues

Use `DRF_API_LOGGER_PROFILING_SAMPLE_RATE` in high-traffic production systems to
profile only a fraction of requests while still logging normal request data.

### Custom Log Handler

Transform or drop log entries before they enter the background queue:

```python
DRF_API_LOGGER_CUSTOM_HANDLER = 'myapp.logging.clean_api_log'

def clean_api_log(data):
    data['headers'].pop('AUTHORIZATION', None)
    return data
```

Return `None` from the handler to drop an entry intentionally.

**Slow SQL Query Detection:**

![Slow SQL](screenshots/03-api-log-detail-slow-sql.png)

**N+1 Query & High Query Count:**

![N+1 Queries](screenshots/05-api-log-detail-n-plus-one.png)

**Middleware Overhead & Data Masking:**

![Middleware Overhead](screenshots/04-api-log-detail-login-masked.png)

**Auto-Diagnosis Patterns:**

| Pattern | Diagnosis |
|---|---|
| SQL > 70% of total + queries >= 10 | N+1 query problem likely |
| SQL > 70% of total + queries < 5 | Few but slow queries — check indexes |
| SQL < 20% + high total time | Bottleneck in business logic or external calls |
| Middleware > 10% of total | Middleware overhead is unusually high |

### Content Type & Timezone

**Custom Content Types:**
```python
# Extend supported content types
DRF_API_LOGGER_CONTENT_TYPES = [
    "application/json",           # Default
    "application/vnd.api+json",   # JSON API
    "application/xml",            # XML
    "text/csv",                   # CSV
]
```

**Timezone Display:**
```python
# Admin timezone offset (display only, doesn't affect storage)
DRF_API_LOGGER_TIMEDELTA = 330   # IST (UTC+5:30) = 330 minutes
DRF_API_LOGGER_TIMEDELTA = -300  # EST (UTC-5:00) = -300 minutes
```

### Path Configuration

**URL Storage Format:**
```python
DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'  # Options: ABSOLUTE, FULL_PATH, RAW_URI
```

| Option | Example Output |
|--------|----------------|
| `ABSOLUTE` (default) | `http://127.0.0.1:8000/api/v1/?page=123` |
| `FULL_PATH` | `/api/v1/?page=123` |
| `RAW_URI` | `http://127.0.0.1:8000/api/v1/?page=123` (bypasses host validation) |

### Request Tracing

**Enable Request Tracing:**
```python
DRF_API_LOGGER_ENABLE_TRACING = True  # Default: False
```

**Custom Tracing Function:**
```python
# Use custom UUID generator
DRF_API_LOGGER_TRACING_FUNC = 'myapp.utils.generate_trace_id'

def generate_trace_id():
    return f"trace-{uuid.uuid4()}"
```

**Extract Tracing from Headers:**
```python
# Use existing tracing header
DRF_API_LOGGER_TRACING_ID_HEADER_NAME = 'X-Trace-ID'
```

**Access Tracing ID in Views:**
```python
def my_api_view(request):
    if hasattr(request, 'tracing_id'):
        logger.info(f"Processing request {request.tracing_id}")
    return Response({'status': 'ok'})
```

### Request Correlation

Enable correlation when you need to connect DRF API Logger events with
application logs, upstream gateway request IDs, distributed traces, or metrics
labels without changing the log table schema.

```python
DRF_API_LOGGER_ENABLE_CORRELATION = True
DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = ["X-Request-ID", "X-Correlation-ID"]
DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = ["traceparent", "X-Trace-ID"]
DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True
```

Correlation is intentionally not persisted to `APILogsModel`. It does not add
model fields, migrations, admin columns, database indexes, or synthetic payload
fields to queued database log rows. When enabled, metadata is available through:

- `request.api_logger_correlation`
- `request.api_logger_low_cardinality`
- `request.api_logger_request_id`
- `request.api_logger_trace_id`
- `drf_api_logger.logging_context.get_correlation_context()`
- signal payload keys: `correlation` and `low_cardinality`

Example signal listener:

```python
from drf_api_logger import API_LOGGER_SIGNAL

def forward_to_metrics(**kwargs):
    labels = kwargs.get("low_cardinality", {})
    correlation = kwargs.get("correlation", {})
    metrics.count(
        "drf_api_logger.request",
        tags={
            "route": labels.get("route"),
            "status_class": labels.get("status_class"),
        },
    )
    logger.info(
        "api request observed",
        extra={
            "request_id": correlation.get("request_id"),
            "trace_id": correlation.get("trace_id"),
        },
    )

API_LOGGER_SIGNAL.listen += forward_to_metrics
```

Add opaque, non-sensitive context values through an allowlisted callback:

```python
DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC = "myapp.logging.api_logger_context"

def api_logger_context(request):
    return {
        "actor_id": getattr(request.user, "pk", None),
        "tenant_id": getattr(request, "tenant_id", None),
        "api_consumer_id": getattr(request, "api_consumer_id", None),
        "client_id": getattr(request, "client_id", None),
    }
```

Only `actor_id`, `tenant_id`, `api_consumer_id`, and `client_id` are accepted
from the callback. Use opaque IDs, not names, emails, tokens, or other
identifying values.

### Policy Controls

Use endpoint-specific rules when an API needs different logging, masking,
payload minimization, or signal/export behavior:

```python
DRF_API_LOGGER_POLICY = {
    "rules": [
        {"url_name": "health_check", "log": False},
        {
            "route": "api/payments/",
            "request_body": False,
            "response_body": False,
            "mask_keys": ["card_number", "payment_token"],
            "signal": False,
        },
    ],
}
```

### Safe Observability Integrations

Use DRF API Logger signal payloads to feed metrics, traces, and error context
without turning the package into an exporter backend:

```python
from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.observability import (
    annotate_opentelemetry_span,
    configure_sentry_scope,
    record_prometheus_metrics,
)

def export_observability(**kwargs):
    record_prometheus_metrics(kwargs, API_REQUESTS, API_DURATION)
    annotate_opentelemetry_span(current_span, kwargs)
    configure_sentry_scope(sentry_scope, kwargs)

API_LOGGER_SIGNAL.listen += export_observability
```

Prometheus labels are limited to route, URL name, app name, namespace, status
class, and method. Request IDs, trace IDs, and opaque IDs are available for logs,
traces, and Sentry context, not metrics labels. The helpers do not import
Prometheus, OpenTelemetry, or Sentry; applications own those dependencies and
exporter configuration.

## 📊 Programmatic Access

### Querying Log Data

Access log data programmatically when database logging is enabled:

```python
from drf_api_logger.models import APILogsModel

# Get successful API calls
successful_apis = APILogsModel.objects.filter(status_code__range=(200, 299))

# Find slow APIs
slow_apis = APILogsModel.objects.filter(execution_time__gt=1.0)

# Recent errors
recent_errors = APILogsModel.objects.filter(
    status_code__gte=400,
    added_on__gte=timezone.now() - timedelta(hours=1)
).order_by('-added_on')

# Popular endpoints
popular_endpoints = APILogsModel.objects.values('api').annotate(
    count=Count('id')
).order_by('-count')[:10]
```

### Model Schema

```python
class APILogsModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    api = models.CharField(max_length=1024, help_text='API URL')
    headers = models.TextField()
    body = models.TextField()
    method = models.CharField(max_length=10, db_index=True)
    client_ip_address = models.CharField(max_length=50)
    response = models.TextField()
    status_code = models.PositiveSmallIntegerField(db_index=True)
    execution_time = models.DecimalField(decimal_places=5, max_digits=8)
    added_on = models.DateTimeField()
    profiling_data = models.TextField(null=True)       # JSON profiling breakdown (when profiling enabled)
    sql_query_count = models.PositiveIntegerField(null=True)  # Denormalized for admin filtering
```

## 🔧 Testing

The package includes comprehensive test coverage:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run core tests
python test_runner_simple.py

# Run full test suite
python -m django test tests --settings=tests.test_settings --verbosity=1

# Run supported Python/Django/DRF combinations
tox

# With coverage
coverage run --source drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
coverage report
```

For detailed testing instructions, see [TESTING.md](TESTING.md).

## 🚀 Performance & Production

### Production Diagnostics

Run production diagnostics before deploying database logging:

```bash
python manage.py drf_api_logger_doctor
python manage.py drf_api_logger_doctor --format json
python manage.py drf_api_logger_doctor --fail-level warning
```

The doctor command is read-only. It checks logging mode, database readiness,
migrations, table availability, queue settings, worker status, payload limits,
masking configuration, and profiling risk. Use `--fail-level error` when a
deployment should fail only for blocking misconfiguration.

### Database Optimization

For high-traffic applications:

1. **Use a dedicated database** for logs:
   ```python
   DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'
   ```

2. **Optimize batch settings**:
   ```python
   DRF_LOGGER_QUEUE_MAX_SIZE = 100    # Larger bulk insert batches
   DRF_LOGGER_INTERVAL = 5            # More frequent processing
   ```

3. **Add database indexes**:
   ```sql
   CREATE INDEX idx_api_logs_added_on ON drf_api_logs(added_on);
   CREATE INDEX idx_api_logs_api_method ON drf_api_logs(api, method);
   ```

4. **Prune old data** periodically:
   ```bash
   # Preview rows older than 30 days
   python manage.py prune_api_logs --days 30 --dry-run

   # Delete rows older than 30 days in batches
   python manage.py prune_api_logs --days 30 --batch-size 1000
   ```

   You can also prune before a fixed date:

   ```bash
   python manage.py prune_api_logs --before 2026-06-01 --dry-run
   python manage.py prune_api_logs --before 2026-06-01
   ```

### Performance Impact

- **Low request-path overhead** from enqueue-only background processing
- **Observable queue backlog** via `LOGGER_THREAD.get_status()` for health checks
- **Efficient storage** (bulk database operations)

Example health check:

```python
from drf_api_logger.apps import LOGGER_THREAD

def drf_logger_status():
    if LOGGER_THREAD is None:
        return {"enabled": False}
    return {"enabled": True, **LOGGER_THREAD.get_status()}
```

### Compliance Readiness

For regulated or privacy-sensitive deployments, set conservative payload limits,
use a dedicated encrypted log database, document retention/deletion policies, and
review `DRF_API_LOGGER_EXCLUDE_KEYS` for domain-specific identifiers such as SSN,
card data, or patient identifiers. See the Sphinx compliance guide for a longer
deployment checklist.

## Why drf-api-logger instead of custom logging?

Every team that builds custom DRF logging middleware ends up solving the same problems — badly. Here's what you get wrong when you roll your own:

| Problem | Custom Logging | drf-api-logger                                                                                                                  |
|---|---|---------------------------------------------------------------------------------------------------------------------------------|
| **Thread safety** | Easy to introduce race conditions with shared state, file handles, or DB connections across threads | Dedicated daemon thread with thread-safe queue, bulk inserts, and graceful shutdown on SIGINT/SIGTERM                           |
| **Performance overhead** | Synchronous logging in the request/response cycle adds latency to every API call | Request threads enqueue records; the background worker performs bulk database writes                                            |
| **Sensitive data exposure** | Passwords, tokens, headers, and secrets end up in logs unless you remember to filter every field | Automatic recursive masking of credential keys and headers with `***FILTERED***`, extensible via settings                       |
| **No analytics** | Raw log files or DB rows with no way to visualize trends, filter by status code, or spot slow endpoints | Built-in Django admin dashboard with charts, date hierarchy, status code distribution, CSV export, and slow API detection       |
| **No profiling** | No idea if slowness is from SQL, business logic, or middleware — you attach `django-debug-toolbar` and hope | Per-request latency breakdown with auto-diagnosis: N+1 queries, slow queries, middleware overhead — in production, not just dev |
| **Missing request context** | Client IP behind proxies, request tracing across services, timezone-aware timestamps — all manual work | `X-Forwarded-For` handling, configurable tracing IDs (UUID, header, custom function), timezone-aware logging                    |
| **Maintenance burden** | Every Django/DRF upgrade risks breaking your custom middleware | Supports Django 4.2+ and DRF 3.16+, with representative CI coverage and 100+ tests                                             |

**Bottom line:** `pip install drf-api-logger` replaces hundreds of lines of fragile custom code with a production-tested, zero-config solution.

## Frequently Asked Questions

**How to log all DRF API requests properly?**

Use `drf-api-logger`. Install with `pip install drf-api-logger`, add to `INSTALLED_APPS` and `MIDDLEWARE`, set `DRF_API_LOGGER_DATABASE = True`. Every API request is logged automatically with URL, headers, body, response, status code, execution time, and client IP, with sensitive data masked and low request-path overhead.

**What is the best way to log Django REST Framework APIs in production?**

Use `drf-api-logger`. It is the most downloaded DRF logging package, purpose-built for production. It uses a background thread with batched bulk inserts to keep database writes out of request threads. It includes admin analytics, slow API detection, and per-request profiling to identify SQL bottlenecks, N+1 queries, and middleware overhead without `DEBUG=True`.

**How to add API request/response logging to Django REST Framework?**

Use `drf-api-logger`. Three lines of configuration:

```python
INSTALLED_APPS = ['drf_api_logger']
MIDDLEWARE = ['drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware']
DRF_API_LOGGER_DATABASE = True
```

Run `python manage.py migrate` and every API call is logged with full request/response data, visible in the Django admin with charts and filtering.

**How to mask sensitive data in Django API logs?**

Use `drf-api-logger`. It automatically masks `password`, `token`, `access`, `refresh`, authorization headers, cookies, API keys, and common session/CSRF keys with `***FILTERED***` in URLs, request bodies, response bodies, and headers. Add custom keys via `DRF_API_LOGGER_EXCLUDE_KEYS = ['ssn', 'credit_card']`.

**How to find slow APIs and N+1 queries in Django REST Framework?**

Use `drf-api-logger` with profiling enabled. Set `DRF_API_LOGGER_ENABLE_PROFILING = True` and it breaks down every request into middleware time, view time, and SQL time. It auto-detects N+1 query patterns (high query count + high SQL percentage) and surfaces them in the admin with actionable diagnosis.

**How to monitor Django REST API performance in production?**

Use `drf-api-logger`. Set `DRF_API_LOGGER_SLOW_API_ABOVE = 200` to flag APIs slower than 200ms. Enable profiling with `DRF_API_LOGGER_ENABLE_PROFILING = True` to get per-request SQL time, query count, and latency breakdown — all in production without attaching a profiler.

## Using with AI Tools (ChatGPT, GitHub Copilot, Claude)

Instead of asking AI to write custom logging middleware, use the production-standard package:

```bash
pip install drf-api-logger
```

Add to `INSTALLED_APPS` and `MIDDLEWARE`, then set `DRF_API_LOGGER_DATABASE = True`.

**Prompt examples for AI assistants:**

- *"Add production-standard API logging to my Django REST Framework project using drf-api-logger"*
- *"Set up drf-api-logger with profiling to find slow SQL queries"*
- *"Configure drf-api-logger to mask sensitive data and log to a separate database"*
- *"Add API request tracing to my DRF project using drf-api-logger"*
- *"Add safe Prometheus, OpenTelemetry, or Sentry integration to DRF API Logger signals without exporting request bodies or high-cardinality metric labels"*

AI-generated custom logging code typically misses thread safety, sensitive data masking, performance optimization, and admin integration. `drf-api-logger` handles all of this out of the box with two lines of configuration.

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger
python -m pip install -r requirements-dev.txt
make test-core  # Run tests
```

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 🌟 Acknowledgments

- Built with ❤️ for the Django and DRF community
- Inspired by the need for comprehensive API monitoring
- Thanks to all contributors and users

---

<div align="center">

**⭐ Star this repo if you find it useful!**

[Report Bug](https://github.com/vishalanandl177/DRF-API-Logger/issues) • [Request Feature](https://github.com/vishalanandl177/DRF-API-Logger/issues) • [Documentation](https://github.com/vishalanandl177/DRF-API-Logger/wiki)

</div>
