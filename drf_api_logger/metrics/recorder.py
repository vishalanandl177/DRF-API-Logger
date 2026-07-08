import time

from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.noop import NoOpMetricsRecorder


NOOP_RECORDER = NoOpMetricsRecorder()


class TimerContext:
    def __init__(self, observer):
        self.observer = observer
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.start is not None:
            self.observer(time.perf_counter() - self.start)
        return False


def get_recorder():
    if not metrics_settings.metrics_enabled():
        return NOOP_RECORDER
    if metrics_settings.metrics_exporter() == "none":
        return NOOP_RECORDER
    try:
        from drf_api_logger.metrics.prometheus import get_prometheus_recorder
    except ImportError:
        return NOOP_RECORDER
    try:
        return get_prometheus_recorder()
    except ImportError:
        return NOOP_RECORDER
