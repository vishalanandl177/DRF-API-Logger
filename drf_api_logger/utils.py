import re
from django.conf import settings


def get_headers(request=None):
    """
        Function:       get_headers(self, request)
        Description:    To get all the headers from request
    """
    regex = re.compile('^HTTP_')
    return dict((regex.sub('', header), value) for (header, value)
                in request.META.items() if header.startswith('HTTP_'))


def get_client_ip(request):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    except:
        return ''


def is_api_logger_enabled():
    drf_api_logger_database = False
    if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
        drf_api_logger_database = settings.DRF_API_LOGGER_DATABASE

    drf_api_logger_signal = False
    if hasattr(settings, 'DRF_API_LOGGER_SIGNAL'):
        drf_api_logger_signal = settings.DRF_API_LOGGER_SIGNAL
    return drf_api_logger_database or drf_api_logger_signal


def database_log_enabled():
    drf_api_logger_database = False
    if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
        drf_api_logger_database = settings.DRF_API_LOGGER_DATABASE
    return drf_api_logger_database
