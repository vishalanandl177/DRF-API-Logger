from django.http import Http404, HttpResponse

from drf_api_logger.metrics import settings as metrics_settings


def generate_prometheus_latest():
    from drf_api_logger.metrics.prometheus import generate_prometheus_latest as generate_latest

    return generate_latest()


def prometheus_metrics_view(request):
    if not metrics_settings.prometheus_endpoint_enabled():
        raise Http404("DRF API Logger metrics endpoint is disabled.")

    payload = generate_prometheus_latest()
    return HttpResponse(
        payload,
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
