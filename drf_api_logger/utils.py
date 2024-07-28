import re
from django.conf import settings
from django.urls import resolve

SENSITIVE_KEYS = ['password', 'token', 'access', 'refresh']
if hasattr(settings, 'DRF_API_LOGGER_EXCLUDE_KEYS'):
    if type(settings.DRF_API_LOGGER_EXCLUDE_KEYS) in (list, tuple):
        SENSITIVE_KEYS.extend(settings.DRF_API_LOGGER_EXCLUDE_KEYS)


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
    except Exception:
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


def mask_sensitive_data(data, mask_api_parameters=False):
    """
    Hides sensitive keys specified in sensitive_keys settings.
    Loops recursively over nested dictionaries.

    When the mask_api_parameters parameter is set, the function will 
    instead iterate over sensitive_keys and remove them from an api 
    URL string.
    """
    if type(data) is not dict:
        if mask_api_parameters and type(data) is str:
            for sensitive_key in SENSITIVE_KEYS:
                data = re.sub('({}=)(.*?)($|&)'.format(sensitive_key),
                              '\\g<1>***FILTERED***\\g<3>'.format(sensitive_key.upper()), data)

        if type(data) is list:
            data = [mask_sensitive_data(item) for item in data]
        return data
    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            data[key] = "***FILTERED***"

        if type(value) is dict:
            data[key] = mask_sensitive_data(data[key])

        if type(value) is list:
            data[key] = [mask_sensitive_data(item) for item in data[key]]

    return data

def get_view_from_request(request):
    try:
        return f"{resolve(request.path_info)._func_path}"[:50]
    except:
        return ""

def get_user(request):
    if hasattr(request, "user") and hasattr(request.user, "is_authenticated"):
        is_authenticated = request.user.is_authenticated
        if is_authenticated:
            return request.user.id
    else:
        return None
