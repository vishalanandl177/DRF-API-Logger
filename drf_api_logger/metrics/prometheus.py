from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.labels import (
    build_http_labels,
    build_http_core_labels,
    build_logger_labels,
    build_security_labels,
)
from drf_api_logger.metrics.recorder import TimerContext


_RECORDER = None


def _prometheus_client():
    try:
        from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest
    except ImportError as exc:
        raise ImportError("Install drf-api-logger[prometheus] to enable Prometheus metrics.") from exc
    return Counter, Gauge, Histogram, CollectorRegistry, generate_latest


def get_prometheus_recorder():
    global _RECORDER
    if _RECORDER is None:
        _RECORDER = PrometheusMetricsRecorder()
    return _RECORDER


def reset_prometheus_recorder_for_tests():
    global _RECORDER
    _RECORDER = None


def generate_prometheus_latest():
    recorder = get_prometheus_recorder()
    _, _, _, _, generate_latest = _prometheus_client()
    return generate_latest(recorder.registry)


class PrometheusMetricsRecorder:
    def __init__(self):
        Counter, Gauge, Histogram, CollectorRegistry, _ = _prometheus_client()
        self.registry = CollectorRegistry()
        namespace = metrics_settings.prometheus_namespace()
        duration_buckets = metrics_settings.histogram_buckets_seconds()
        size_buckets = metrics_settings.histogram_buckets_bytes()

        http_labels = ("method", "route", "view_name", "status_class")
        active_http_labels = ("method", "route")
        self.http_requests = Counter(
            "http_requests",
            "DRF API Logger observed HTTP requests.",
            http_labels,
            namespace=namespace,
            registry=self.registry,
        )
        self.http_active_requests = Gauge(
            "http_active_requests",
            "In-flight HTTP requests observed by DRF API Logger.",
            active_http_labels,
            namespace=namespace,
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "http_request_duration_seconds",
            "DRF API Logger observed HTTP request duration.",
            http_labels,
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.http_request_body_size = Histogram(
            "http_request_body_size_bytes",
            "Observed request body size from Content-Length or bounded request metadata.",
            ("method", "route"),
            namespace=namespace,
            registry=self.registry,
            buckets=size_buckets,
        )
        self.http_response_body_size = Histogram(
            "http_response_body_size_bytes",
            "Observed non-streaming response body size.",
            ("method", "route", "status_class"),
            namespace=namespace,
            registry=self.registry,
            buckets=size_buckets,
        )
        self.http_slow_requests = Counter(
            "http_slow_requests",
            "Requests at or above DRF_API_LOGGER_SLOW_API_ABOVE.",
            ("method", "route", "view_name"),
            namespace=namespace,
            registry=self.registry,
        )
        self.http_exceptions = Counter(
            "http_exceptions",
            "Exceptions raised during observed request processing.",
            ("route", "exception_class", "status_code"),
            namespace=namespace,
            registry=self.registry,
        )
        self.http_throttled_requests = Counter(
            "http_throttled_requests",
            "HTTP 429 responses observed by DRF API Logger.",
            ("route", "throttle_scope"),
            namespace=namespace,
            registry=self.registry,
        )
        self.logger_overhead = Histogram(
            "request_overhead_seconds",
            "Estimated DRF API Logger request-path overhead.",
            ("route", "logging_enabled"),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.payload_capture_duration = Histogram(
            "payload_capture_duration_seconds",
            "Time spent capturing request or response payloads.",
            ("location",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.masking_duration = Histogram(
            "masking_duration_seconds",
            "Time spent masking sensitive data.",
            ("location",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.serialization_duration = Histogram(
            "serialization_duration_seconds",
            "Time spent serializing log payloads.",
            ("payload",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.enqueue_duration = Histogram(
            "enqueue_duration_seconds",
            "Time spent enqueueing API log records.",
            ("queue_name",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.enqueued_logs = Counter(
            "log_events_enqueued",
            "API log records accepted into the background queue.",
            ("queue_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.processed_logs = Counter(
            "log_events_processed",
            "API log records persisted by the background worker.",
            ("storage_backend",),
            namespace=namespace,
            registry=self.registry,
        )
        self.dropped_logs = Counter(
            "log_events_dropped",
            "API log records dropped before persistence.",
            ("reason",),
            namespace=namespace,
            registry=self.registry,
        )
        self.skipped_logs = Counter(
            "log_events_skipped",
            "API log records skipped by policy.",
            ("reason",),
            namespace=namespace,
            registry=self.registry,
        )
        self.queue_depth = Gauge(
            "queue_depth",
            "Current API logger queue backlog.",
            ("queue_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.queue_capacity = Gauge(
            "queue_capacity",
            "Configured API logger queue batch threshold.",
            ("queue_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.queue_utilization = Gauge(
            "queue_utilization_ratio",
            "Current API logger queue depth divided by configured capacity.",
            ("queue_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.worker_up = Gauge(
            "worker_up",
            "Whether the background API logger worker is alive.",
            ("worker_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.worker_restarts = Counter(
            "worker_restarts",
            "Background API logger worker starts observed in this process.",
            ("worker_name",),
            namespace=namespace,
            registry=self.registry,
        )
        self.flush_duration = Histogram(
            "flush_duration_seconds",
            "Background worker batch flush duration.",
            ("storage_backend",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.flush_batch_size = Histogram(
            "flush_batch_size",
            "Background worker batch size.",
            ("storage_backend",),
            namespace=namespace,
            registry=self.registry,
        )
        self.storage_write_failures = Counter(
            "storage_write_failures",
            "Failed storage writes by backend and exception class.",
            ("storage_backend", "exception_class"),
            namespace=namespace,
            registry=self.registry,
        )
        self.storage_write_duration = Histogram(
            "storage_write_duration_seconds",
            "Storage sink write duration.",
            ("storage_backend",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.sql_duration = Histogram(
            "request_sql_duration_seconds",
            "SQL duration observed from DRF API Logger profiling data.",
            ("route", "view_name"),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.sql_queries = Histogram(
            "request_sql_queries",
            "SQL query count observed from DRF API Logger profiling data.",
            ("route", "view_name"),
            namespace=namespace,
            registry=self.registry,
        )
        self.duplicate_sql_queries = Histogram(
            "request_duplicate_sql_queries",
            "Duplicate SQL query count observed from profiling data.",
            ("route", "view_name"),
            namespace=namespace,
            registry=self.registry,
        )
        self.n_plus_one_suspected = Counter(
            "n_plus_one_suspected",
            "Requests whose profiling data indicates a likely N+1 query pattern.",
            ("route", "view_name"),
            namespace=namespace,
            registry=self.registry,
        )
        self.view_duration = Histogram(
            "view_duration_seconds",
            "View and serialization duration from profiling data.",
            ("route", "view_name"),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.middleware_duration = Histogram(
            "middleware_duration_seconds",
            "Middleware duration from profiling data.",
            ("middleware_name",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        security_labels = (
            "event_type",
            "category",
            "severity",
            "route",
            "method",
            "status_class",
            "outcome",
        )
        self.security_events = Counter(
            "security_events",
            "Security or suspicious activity events observed.",
            security_labels,
            namespace=namespace,
            registry=self.registry,
        )
        self.security_rule_matches = Counter(
            "security_rule_matches",
            "Security rule matches observed.",
            ("rule_id", "category", "severity", "route", "method"),
            namespace=namespace,
            registry=self.registry,
        )
        self.security_risk_score = Histogram(
            "security_request_risk_score",
            "Request-level security risk score distribution.",
            ("route", "method", "status_class"),
            namespace=namespace,
            registry=self.registry,
        )
        self.security_detection_duration = Histogram(
            "security_detection_duration_seconds",
            "Security detection engine duration.",
            ("route",),
            namespace=namespace,
            registry=self.registry,
            buckets=duration_buckets,
        )
        self.security_detection_errors = Counter(
            "security_detection_errors",
            "Security detection errors isolated from the request path.",
            ("rule_id", "exception_class"),
            namespace=namespace,
            registry=self.registry,
        )
        self.security_alerts = Counter(
            "security_alerts",
            "Security events at warning severity or above.",
            ("category", "severity", "route"),
            namespace=namespace,
            registry=self.registry,
        )
        self.auth_failure_bursts = Counter(
            "auth_failure_bursts",
            "Authentication abuse or success-after-failure signals.",
            ("route",),
            namespace=namespace,
            registry=self.registry,
        )
        self.route_scan_suspected = Counter(
            "route_scan_suspected",
            "Route scanning signals observed.",
            ("route",),
            namespace=namespace,
            registry=self.registry,
        )
        self.object_id_enumeration_suspected = Counter(
            "object_id_enumeration_suspected",
            "Object ID enumeration signals observed.",
            ("route",),
            namespace=namespace,
            registry=self.registry,
        )
        self.payload_attack_pattern_matches = Counter(
            "payload_attack_pattern_matches",
            "Payload attack pattern signals observed.",
            ("attack_type", "route"),
            namespace=namespace,
            registry=self.registry,
        )
        self.high_response_volume_suspected = Counter(
            "high_response_volume_suspected",
            "High response volume or export-like signals observed.",
            ("route",),
            namespace=namespace,
            registry=self.registry,
        )

    def timer(self, name, labels=None):
        labels = labels or {}
        if name == "payload_capture":
            return TimerContext(
                lambda duration: self.observe_payload_capture(
                    labels,
                    labels.get("location", "unknown"),
                    duration,
                )
            )
        if name == "masking":
            return TimerContext(
                lambda duration: self.observe_masking(
                    labels,
                    labels.get("location", "unknown"),
                    duration,
                )
            )
        if name == "serialization":
            return TimerContext(lambda duration: self.observe_serialization(labels, duration))
        if name == "enqueue":
            return TimerContext(lambda duration: self.observe_enqueue(labels, duration))
        return TimerContext(lambda duration: None)

    def increment_active_requests(self, labels):
        if not metrics_settings.api_metrics_enabled():
            return
        safe = build_http_core_labels({"method": labels.get("method"), "low_cardinality": labels})
        self.http_active_requests.labels(
            method=safe.get("method", "unknown"),
            route=safe.get("route", "unknown"),
        ).inc()

    def decrement_active_requests(self, labels):
        if not metrics_settings.api_metrics_enabled():
            return
        safe = build_http_core_labels({"method": labels.get("method"), "low_cardinality": labels})
        self.http_active_requests.labels(
            method=safe.get("method", "unknown"),
            route=safe.get("route", "unknown"),
        ).dec()

    def observe_http_request(self, event):
        if not metrics_settings.api_metrics_enabled():
            return
        labels = build_http_labels(event)
        core = build_http_core_labels(event)
        projected = {
            "method": core.get("method", labels.get("method", "unknown")),
            "route": core.get("route", labels.get("route", "unknown")),
            "view_name": core.get("view_name", labels.get("view_name", "unknown")),
            "status_class": core.get("status_class", labels.get("status_class", "unknown")),
        }
        self.http_requests.labels(**projected).inc()
        duration = event.get("execution_time")
        if isinstance(duration, (int, float)) and duration >= 0:
            self.http_duration.labels(**projected).observe(duration)
        request_body_size = event.get("request_body_size_bytes")
        if isinstance(request_body_size, int) and request_body_size >= 0:
            self.http_request_body_size.labels(
                method=projected["method"],
                route=projected["route"],
            ).observe(request_body_size)
        response_body_size = event.get("response_body_size_bytes")
        if isinstance(response_body_size, int) and response_body_size >= 0:
            self.http_response_body_size.labels(
                method=projected["method"],
                route=projected["route"],
                status_class=projected["status_class"],
            ).observe(response_body_size)
        if event.get("is_slow") is True:
            self.http_slow_requests.labels(
                method=projected["method"],
                route=projected["route"],
                view_name=projected["view_name"],
            ).inc()
        if str(event.get("status_code")) == "429":
            self.http_throttled_requests.labels(
                route=projected["route"],
                throttle_scope=core.get("throttle_scope", "unknown"),
            ).inc()

    def increment_http_exception(self, event):
        if not metrics_settings.api_metrics_enabled():
            return
        core = build_http_core_labels(event)
        self.http_exceptions.labels(
            route=core.get("route", "unknown"),
            exception_class=core.get("exception_class", "Exception"),
            status_code=core.get("status_code", "500"),
        ).inc()

    def observe_logger_overhead(self, labels, duration_seconds):
        if not metrics_settings.logger_metrics_enabled():
            return
        safe = build_logger_labels(labels)
        self.logger_overhead.labels(
            route=safe.get("route", "unknown"),
            logging_enabled=safe.get("logging_enabled", "unknown"),
        ).observe(max(float(duration_seconds), 0.0))

    def observe_payload_capture(self, labels, location, duration_seconds):
        if metrics_settings.logger_metrics_enabled():
            self.payload_capture_duration.labels(location=str(location or "unknown")).observe(
                max(float(duration_seconds), 0.0)
            )

    def observe_masking(self, labels, location, duration_seconds):
        if metrics_settings.logger_metrics_enabled():
            self.masking_duration.labels(location=str(location or "unknown")).observe(
                max(float(duration_seconds), 0.0)
            )

    def observe_serialization(self, labels, duration_seconds):
        if metrics_settings.logger_metrics_enabled():
            safe = build_logger_labels(labels)
            self.serialization_duration.labels(payload=safe.get("payload", "unknown")).observe(
                max(float(duration_seconds), 0.0)
            )

    def observe_enqueue(self, labels, duration_seconds):
        if metrics_settings.pipeline_metrics_enabled():
            safe = build_logger_labels(labels)
            self.enqueue_duration.labels(queue_name=safe.get("queue_name", "default")).observe(
                max(float(duration_seconds), 0.0)
            )

    def increment_enqueued_logs(self, queue_name="default"):
        if metrics_settings.pipeline_metrics_enabled():
            self.enqueued_logs.labels(queue_name=str(queue_name or "default")).inc()

    def increment_processed_logs(self, storage_backend, count):
        if metrics_settings.pipeline_metrics_enabled():
            self.processed_logs.labels(storage_backend=str(storage_backend or "database")).inc(count)

    def increment_dropped_logs(self, reason):
        if metrics_settings.pipeline_metrics_enabled():
            self.dropped_logs.labels(reason=str(reason or "unknown")).inc()

    def increment_skipped_logs(self, reason):
        if metrics_settings.pipeline_metrics_enabled():
            self.skipped_logs.labels(reason=str(reason or "unknown")).inc()

    def increment_storage_write_failure(self, storage_backend, exception_class):
        if metrics_settings.pipeline_metrics_enabled():
            self.storage_write_failures.labels(
                storage_backend=str(storage_backend or "database"),
                exception_class=str(exception_class or "Exception"),
            ).inc()

    def set_queue_depth(self, queue_name, depth):
        if metrics_settings.pipeline_metrics_enabled():
            self.queue_depth.labels(queue_name=str(queue_name or "default")).set(max(int(depth), 0))

    def set_queue_capacity(self, queue_name, capacity):
        if metrics_settings.pipeline_metrics_enabled():
            self.queue_capacity.labels(queue_name=str(queue_name or "default")).set(max(int(capacity), 0))

    def set_queue_utilization(self, queue_name, ratio):
        if metrics_settings.pipeline_metrics_enabled():
            try:
                ratio = float(ratio)
            except (TypeError, ValueError):
                ratio = 0.0
            self.queue_utilization.labels(queue_name=str(queue_name or "default")).set(max(ratio, 0.0))

    def set_worker_up(self, worker_name, up):
        if metrics_settings.pipeline_metrics_enabled():
            self.worker_up.labels(worker_name=str(worker_name or "worker")).set(1 if up else 0)

    def increment_worker_restart(self, worker_name):
        if metrics_settings.pipeline_metrics_enabled():
            self.worker_restarts.labels(worker_name=str(worker_name or "worker")).inc()

    def observe_flush(self, storage_backend, duration_seconds, batch_size):
        if metrics_settings.pipeline_metrics_enabled():
            backend = str(storage_backend or "database")
            self.flush_duration.labels(storage_backend=backend).observe(max(float(duration_seconds), 0.0))
            self.flush_batch_size.labels(storage_backend=backend).observe(max(int(batch_size), 0))

    def observe_storage_write(self, storage_backend, duration_seconds):
        if metrics_settings.pipeline_metrics_enabled():
            backend = str(storage_backend or "database")
            self.storage_write_duration.labels(storage_backend=backend).observe(max(float(duration_seconds), 0.0))

    def observe_profiling(self, labels, profiling):
        if not metrics_settings.profiling_metrics_enabled():
            return
        safe = build_logger_labels(labels)
        route = safe.get("route", "unknown")
        view_name = safe.get("view_name", "unknown")
        sql = profiling.get("sql") or {}
        sql_time = sql.get("total_time")
        query_count = sql.get("query_count")
        duplicate_queries = sql.get("duplicate_query_count")
        if isinstance(sql_time, (int, float)) and sql_time >= 0:
            self.sql_duration.labels(route=route, view_name=view_name).observe(sql_time)
        if isinstance(query_count, int) and query_count >= 0:
            self.sql_queries.labels(route=route, view_name=view_name).observe(query_count)
        if isinstance(duplicate_queries, int) and duplicate_queries >= 0:
            self.duplicate_sql_queries.labels(route=route, view_name=view_name).observe(duplicate_queries)
        view_duration = profiling.get("view_and_serialization")
        if isinstance(view_duration, (int, float)) and view_duration >= 0:
            self.view_duration.labels(route=route, view_name=view_name).observe(view_duration)
        middleware_before = profiling.get("middleware_before_view")
        if isinstance(middleware_before, (int, float)) and middleware_before >= 0:
            self.middleware_duration.labels(middleware_name="before_view").observe(middleware_before)
        middleware_after = profiling.get("middleware_after_view")
        if isinstance(middleware_after, (int, float)) and middleware_after >= 0:
            self.middleware_duration.labels(middleware_name="after_view").observe(middleware_after)
        if isinstance(query_count, int) and isinstance(sql_time, (int, float)):
            total = profiling.get("view_and_serialization") or 0
            sql_pct = (sql_time / total) * 100 if total > 0 else 0
            if sql_pct > 70 and query_count >= 10:
                self.n_plus_one_suspected.labels(route=route, view_name=view_name).inc()

    def observe_security_event(self, signal):
        if not metrics_settings.security_metrics_enabled():
            return
        labels = build_security_labels(signal)
        self.security_events.labels(
            event_type=labels["event_type"],
            category=labels["category"],
            severity=labels["severity"],
            route=labels["route"],
            method=labels["method"],
            status_class=labels["status_class"],
            outcome=labels["outcome"],
        ).inc()
        self.security_rule_matches.labels(
            rule_id=labels["rule_id"],
            category=labels["category"],
            severity=labels["severity"],
            route=labels["route"],
            method=labels["method"],
        ).inc()
        self.security_risk_score.labels(
            route=labels["route"],
            method=labels["method"],
            status_class=labels["status_class"],
        ).observe(max(int(signal.score), 0))
        if labels["severity"] in {"warning", "error", "critical"}:
            self.security_alerts.labels(
                category=labels["category"],
                severity=labels["severity"],
                route=labels["route"],
            ).inc()
        if signal.event_type in {"auth_failure", "success_after_auth_failures", "token_failure_burst"}:
            self.auth_failure_bursts.labels(route=labels["route"]).inc()
        if signal.event_type == "route_scan_suspected":
            self.route_scan_suspected.labels(route=labels["route"]).inc()
        if signal.event_type == "object_id_enumeration_suspected":
            self.object_id_enumeration_suspected.labels(route=labels["route"]).inc()
        if signal.event_type in {"payload_attack_pattern", "log_injection_attempt"}:
            self.payload_attack_pattern_matches.labels(
                attack_type=labels["reason"],
                route=labels["route"],
            ).inc()
        if signal.event_type in {"high_response_volume_suspected", "bulk_export_suspected"}:
            self.high_response_volume_suspected.labels(route=labels["route"]).inc()

    def observe_security_detection(self, labels, duration_seconds):
        if metrics_settings.security_metrics_enabled():
            safe = build_logger_labels(labels)
            self.security_detection_duration.labels(route=safe.get("route", "unknown")).observe(
                max(float(duration_seconds), 0.0)
            )

    def increment_security_detection_error(self, rule_id, exception_class):
        if metrics_settings.security_metrics_enabled():
            self.security_detection_errors.labels(
                rule_id=str(rule_id or "unknown"),
                exception_class=str(exception_class or "Exception"),
            ).inc()
