from django.urls import path

from drf_api_logger.metrics import settings as metrics_settings
from drf_api_logger.metrics.views import prometheus_metrics_view


urlpatterns = [
    path(
        metrics_settings.prometheus_endpoint_path(),
        prometheus_metrics_view,
        name="drf_api_logger_prometheus_metrics",
    ),
]
