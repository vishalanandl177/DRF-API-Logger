import json
from django.http import HttpResponse
from drf_api_logger.metrics import get_metrics, format_prometheus


def metrics_json(request):
    data = get_metrics()
    return HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json',
    )


def metrics_prometheus(request):
    return HttpResponse(
        format_prometheus(),
        content_type='text/plain; version=0.0.4; charset=utf-8',
    )
