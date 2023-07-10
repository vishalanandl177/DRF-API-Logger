import importlib
import json
import time
import uuid

from django.conf import settings
from django.urls import resolve
from django.utils import timezone

from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.start_logger_when_server_starts import LOGGER_THREAD
from drf_api_logger.utils import get_headers, get_client_ip, mask_sensitive_data

"""
File: api_logger_middleware.py
Class: APILoggerMiddleware
"""


class APILoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

        self.DRF_API_LOGGER_DATABASE = False
        if hasattr(settings, 'DRF_API_LOGGER_DATABASE'):
            self.DRF_API_LOGGER_DATABASE = settings.DRF_API_LOGGER_DATABASE

        self.DRF_API_LOGGER_SIGNAL = False
        if hasattr(settings, 'DRF_API_LOGGER_SIGNAL'):
            self.DRF_API_LOGGER_SIGNAL = settings.DRF_API_LOGGER_SIGNAL

        self.DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'
        if hasattr(settings, 'DRF_API_LOGGER_PATH_TYPE'):
            if settings.DRF_API_LOGGER_PATH_TYPE in ['ABSOLUTE', 'RAW_URI', 'FULL_PATH']:
                self.DRF_API_LOGGER_PATH_TYPE = settings.DRF_API_LOGGER_PATH_TYPE

        self.DRF_API_LOGGER_SKIP_URL_NAME = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_URL_NAME'):
            if type(settings.DRF_API_LOGGER_SKIP_URL_NAME) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_URL_NAME) is list:
                self.DRF_API_LOGGER_SKIP_URL_NAME = settings.DRF_API_LOGGER_SKIP_URL_NAME

        self.DRF_API_LOGGER_SKIP_NAMESPACE = []
        if hasattr(settings, 'DRF_API_LOGGER_SKIP_NAMESPACE'):
            if type(settings.DRF_API_LOGGER_SKIP_NAMESPACE) is tuple or type(
                    settings.DRF_API_LOGGER_SKIP_NAMESPACE) is list:
                self.DRF_API_LOGGER_SKIP_NAMESPACE = settings.DRF_API_LOGGER_SKIP_NAMESPACE

        self.DRF_API_LOGGER_METHODS = []
        if hasattr(settings, 'DRF_API_LOGGER_METHODS'):
            if type(settings.DRF_API_LOGGER_METHODS) is tuple or type(
                    settings.DRF_API_LOGGER_METHODS) is list:
                self.DRF_API_LOGGER_METHODS = settings.DRF_API_LOGGER_METHODS

        self.DRF_API_LOGGER_STATUS_CODES = []
        if hasattr(settings, 'DRF_API_LOGGER_STATUS_CODES'):
            if type(settings.DRF_API_LOGGER_STATUS_CODES) is tuple or type(
                    settings.DRF_API_LOGGER_STATUS_CODES) is list:
                self.DRF_API_LOGGER_STATUS_CODES = settings.DRF_API_LOGGER_STATUS_CODES

        self.DRF_API_LOGGER_ENABLE_TRACING = False
        self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME = None
        if hasattr(settings, 'DRF_API_LOGGER_ENABLE_TRACING'):
            self.DRF_API_LOGGER_ENABLE_TRACING = settings.DRF_API_LOGGER_ENABLE_TRACING
            if self.DRF_API_LOGGER_ENABLE_TRACING and hasattr(settings, 'DRF_API_LOGGER_TRACING_ID_HEADER_NAME'):
                self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME = settings.DRF_API_LOGGER_TRACING_ID_HEADER_NAME

        self.tracing_func_name = None
        if hasattr(settings, 'DRF_API_LOGGER_TRACING_FUNC'):
            mod_name, func_name = settings.DRF_API_LOGGER_TRACING_FUNC.rsplit('.', 1)
            mod = importlib.import_module(mod_name)
            self.tracing_func_name = getattr(mod, func_name)

    def __call__(self, request):

        # Run only if logger is enabled.
        if self.DRF_API_LOGGER_DATABASE or self.DRF_API_LOGGER_SIGNAL:

            url_name = resolve(request.path_info).url_name
            namespace = resolve(request.path_info).namespace

            # Always skip Admin panel
            if namespace == 'admin':
                return self.get_response(request)

            # Skip for url name
            if url_name in self.DRF_API_LOGGER_SKIP_URL_NAME:
                return self.get_response(request)

            # Skip entire app using namespace
            if namespace in self.DRF_API_LOGGER_SKIP_NAMESPACE:
                return self.get_response(request)

            # Code to be executed for each request/response after
            # the view is called.

            start_time = time.time()

            headers = get_headers(request=request)
            method = request.method

            request_data = ''
            try:
                request_data = json.loads(request.body) if request.body else ''
            except:
                pass

            tracing_id = None
            if self.DRF_API_LOGGER_ENABLE_TRACING:
                if self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME:
                    tracing_id = headers.get(self.DRF_API_LOGGER_TRACING_ID_HEADER_NAME)
                if not tracing_id:
                    """
                    If tracing is is not present in header, get it from function or uuid.
                    """
                    if self.tracing_func_name:
                        tracing_id = self.tracing_func_name()
                    else:
                        tracing_id = str(uuid.uuid4())
                request.tracing_id = tracing_id

            # Code to be executed for each request before
            # the view (and later middleware) are called.
            response = self.get_response(request)

            # Only log required status codes if matching
            if self.DRF_API_LOGGER_STATUS_CODES and response.status_code not in self.DRF_API_LOGGER_STATUS_CODES:
                return response

            # Log only registered methods if available.
            if len(self.DRF_API_LOGGER_METHODS) > 0 and method not in self.DRF_API_LOGGER_METHODS:
                return response

            if response.get('content-type') in (
                    'application/json', 'application/vnd.api+json', 'application/gzip', 'application/octet-stream'):

                if response.get('content-type') == 'application/gzip':
                    response_body = '** GZIP Archive **'
                elif response.get('content-type') == 'application/octet-stream':
                    response_body = '** Binary File **'
                elif getattr(response, 'streaming', False):
                    response_body = '** Streaming **'
                else:
                    if type(response.content) == bytes:
                        response_body = json.loads(response.content.decode())
                    else:
                        response_body = json.loads(response.content)
                if self.DRF_API_LOGGER_PATH_TYPE == 'ABSOLUTE':
                    api = request.build_absolute_uri()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'FULL_PATH':
                    api = request.get_full_path()
                elif self.DRF_API_LOGGER_PATH_TYPE == 'RAW_URI':
                    api = request.get_raw_uri()
                else:
                    api = request.build_absolute_uri()

                data = dict(
                    api=mask_sensitive_data(api, mask_api_parameters=True),
                    headers=mask_sensitive_data(headers),
                    body=mask_sensitive_data(request_data),
                    method=method,
                    client_ip_address=get_client_ip(request),
                    response=mask_sensitive_data(response_body),
                    status_code=response.status_code,
                    execution_time=time.time() - start_time,
                    added_on=timezone.now()
                )
                if self.DRF_API_LOGGER_DATABASE:
                    if LOGGER_THREAD:
                        d = data.copy()
                        d['headers'] = json.dumps(d['headers'], indent=4, ensure_ascii=False)
                        if request_data:
                            d['body'] = json.dumps(d['body'], indent=4, ensure_ascii=False)
                        d['response'] = json.dumps(d['response'], indent=4, ensure_ascii=False)
                        LOGGER_THREAD.put_log_data(data=d)
                if self.DRF_API_LOGGER_SIGNAL:
                    if tracing_id:
                        data.update({
                            'tracing_id': tracing_id
                        })
                    API_LOGGER_SIGNAL.listen(**data)
            else:
                return response
        else:
            response = self.get_response(request)
        return response
