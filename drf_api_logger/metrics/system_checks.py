import importlib.util
import os

from django.core.checks import Error, Warning, register

from drf_api_logger.metrics import settings as metrics_settings


@register()
def check_metrics_configuration(app_configs, **kwargs):
    messages = []
    if not metrics_settings.metrics_enabled():
        return messages

    if (
        metrics_settings.metrics_exporter() == "prometheus"
        and importlib.util.find_spec("prometheus_client") is None
    ):
        messages.append(
            Error(
                "Prometheus metrics are enabled but prometheus_client is not installed.",
                hint="Install drf-api-logger[prometheus] or set DRF_API_LOGGER_METRICS_EXPORTER='none'.",
                id="drf_api_logger.E701",
            )
        )

    unsafe_labels = metrics_settings.unsafe_metric_label_keys()
    if unsafe_labels:
        messages.append(
            Error(
                "Unsafe metric labels are configured: {}.".format(", ".join(unsafe_labels)),
                hint="Use only low-cardinality labels such as method, route, view_name, and status_class.",
                id="drf_api_logger.E702",
            )
        )

    if metrics_settings.prometheus_endpoint_enabled():
        messages.append(
            Warning(
                "The DRF API Logger Prometheus endpoint is enabled.",
                hint="Expose it only on an internal network, behind authentication, or through a protected scrape path.",
                id="drf_api_logger.W703",
            )
        )

    if (
        metrics_settings.metrics_exporter() == "prometheus"
        and not os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        and (
            os.environ.get("WEB_CONCURRENCY")
            or os.environ.get("GUNICORN_CMD_ARGS")
            or os.environ.get("UWSGI_ORIGINAL_PROC_NAME")
        )
    ):
        messages.append(
            Warning(
                "Prometheus metrics appear to be enabled in a multiprocess deployment.",
                hint="Configure prometheus_client multiprocess mode or scrape each process separately.",
                id="drf_api_logger.W705",
            )
        )

    if metrics_settings.security_metrics_enabled():
        body_config = metrics_settings.security_body_inspection_config()
        max_body_bytes = body_config.get("max_body_bytes")
        if not isinstance(max_body_bytes, int) or isinstance(max_body_bytes, bool) or max_body_bytes < 0:
            messages.append(
                Error(
                    "Security body inspection must use a finite non-negative max_body_bytes value.",
                    hint="Set DRF_API_LOGGER_SECURITY_BODY_INSPECTION['max_body_bytes'] to 8192 or another finite byte count.",
                    id="drf_api_logger.E704",
                )
            )

    return messages
