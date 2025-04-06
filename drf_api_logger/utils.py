import re
from django.conf import settings

# Default list of sensitive keys to filter from logs or API data.
SENSITIVE_KEYS = ['password', 'token', 'access', 'refresh']

# Extend the sensitive keys if additional keys are provided in Django settings.
if hasattr(settings, 'DRF_API_LOGGER_EXCLUDE_KEYS'):
    if type(settings.DRF_API_LOGGER_EXCLUDE_KEYS) in (list, tuple):
        SENSITIVE_KEYS.extend(settings.DRF_API_LOGGER_EXCLUDE_KEYS)


def get_headers(request=None):
    """
    Extracts and returns HTTP headers from the request object.

    Parameters:
    -----------
    request : HttpRequest
        The Django request object from which headers are extracted.

    Returns:
    --------
    dict
        A dictionary of header keys and values. Only headers starting with 'HTTP_' are included.
        'HTTP_' prefix is removed from the header names.
    """
    regex = re.compile('^HTTP_')
    return dict((regex.sub('', header), value)
                for (header, value) in request.META.items()
                if header.startswith('HTTP_'))


def get_client_ip(request):
    """
    Retrieves the client's IP address from the request.

    Parameters:
    -----------
    request : HttpRequest
        The incoming request object.

    Returns:
    --------
    str
        The client's IP address. Returns an empty string if IP can't be determined.
    """
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # If multiple IPs are present (proxy), take the first one
            ip = x_forwarded_for.split(',')[0]
        else:
            # Fallback to direct remote address
            ip = request.META.get('REMOTE_ADDR')
        return ip
    except Exception:
        return ''


def is_api_logger_enabled():
    """
    Checks if any form of API logging (signal or database) is enabled.

    Returns:
    --------
    bool
        True if either `DRF_API_LOGGER_DATABASE` or `DRF_API_LOGGER_SIGNAL` is enabled in settings.
    """
    drf_api_logger_database = False
    if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
        drf_api_logger_database = settings.DRF_API_LOGGER_DATABASE

    drf_api_logger_signal = False
    if hasattr(settings, 'DRF_API_LOGGER_SIGNAL'):
        drf_api_logger_signal = settings.DRF_API_LOGGER_SIGNAL

    return drf_api_logger_database or drf_api_logger_signal


def database_log_enabled():
    """
    Checks if database-based logging is enabled.

    Returns:
    --------
    bool
        True if `DRF_API_LOGGER_DATABASE` is set to True in settings.
    """
    drf_api_logger_database = False
    if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
        drf_api_logger_database = settings.DRF_API_LOGGER_DATABASE
    return drf_api_logger_database


def mask_sensitive_data(data, mask_api_parameters=False):
    """
    Masks or removes sensitive data such as passwords or tokens from dictionaries or URL strings.

    Parameters:
    -----------
    data : dict, str, list
        The input data to be cleaned. Can be a dictionary, list of dicts, or URL string.
    mask_api_parameters : bool
        If True, applies masking to query parameters in a string (URL format).
        Otherwise, it recursively filters keys from dictionaries/lists.

    Returns:
    --------
    dict, str, list
        The sanitized version of the input data, with sensitive values replaced by "***FILTERED***".
    """
    if type(data) is not dict:
        # Handle query string case if enabled
        if mask_api_parameters and type(data) is str:
            for sensitive_key in SENSITIVE_KEYS:
                # Replaces values like token=abcd1234& -> token=***FILTERED***&
                data = re.sub(
                    '({}=)(.*?)($|&)'.format(sensitive_key),
                    r'\1***FILTERED***\3',
                    data
                )

        # If it's a list, sanitize each item recursively
        if type(data) is list:
            data = [mask_sensitive_data(item) for item in data]
        return data

    # Process each key-value pair in the dictionary
    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            data[key] = "***FILTERED***"  # Mask sensitive keys

        elif type(value) is dict:
            data[key] = mask_sensitive_data(data[key])  # Recurse into nested dict

        elif type(value) is list:
            data[key] = [mask_sensitive_data(item) for item in data[key]]  # Recurse into list

    return data
