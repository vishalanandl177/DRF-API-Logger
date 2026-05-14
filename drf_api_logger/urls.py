from django.urls import path
from drf_api_logger.views import metrics_json, metrics_prometheus

app_name = 'drf_api_logger'

urlpatterns = [
    path('metrics/', metrics_prometheus, name='metrics'),
    path('metrics/json/', metrics_json, name='metrics-json'),
]
