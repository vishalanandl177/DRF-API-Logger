from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LoggerConfig(AppConfig):
    name = 'drf_api_logger'
    verbose_name = _('DRF API Logger')
    verbose_name_plural = _('DRF API Logger')
