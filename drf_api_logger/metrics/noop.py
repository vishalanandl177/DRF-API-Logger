class NoOpTimer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class NoOpMetricsRecorder:
    def timer(self, name, labels=None):
        return NoOpTimer()

    def observe_http_request(self, event):
        return None

    def increment_active_requests(self, labels):
        return None

    def decrement_active_requests(self, labels):
        return None

    def increment_http_exception(self, event):
        return None

    def observe_logger_overhead(self, labels, duration_seconds):
        return None

    def observe_payload_capture(self, labels, location, duration_seconds):
        return None

    def observe_masking(self, labels, location, duration_seconds):
        return None

    def observe_serialization(self, labels, duration_seconds):
        return None

    def observe_enqueue(self, labels, duration_seconds):
        return None

    def increment_enqueued_logs(self, queue_name="default"):
        return None

    def increment_processed_logs(self, storage_backend, count):
        return None

    def increment_dropped_logs(self, reason):
        return None

    def increment_skipped_logs(self, reason):
        return None

    def increment_storage_write_failure(self, storage_backend, exception_class):
        return None

    def set_queue_depth(self, queue_name, depth):
        return None

    def set_queue_capacity(self, queue_name, capacity):
        return None

    def set_queue_utilization(self, queue_name, ratio):
        return None

    def set_worker_up(self, worker_name, up):
        return None

    def increment_worker_restart(self, worker_name):
        return None

    def observe_flush(self, storage_backend, duration_seconds, batch_size):
        return None

    def observe_storage_write(self, storage_backend, duration_seconds):
        return None

    def observe_profiling(self, labels, profiling):
        return None

    def observe_security_event(self, signal):
        return None

    def observe_security_detection(self, labels, duration_seconds):
        return None

    def increment_security_detection_error(self, rule_id, exception_class):
        return None
