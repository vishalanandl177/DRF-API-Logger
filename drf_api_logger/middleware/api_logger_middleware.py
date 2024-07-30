import importlib
import json
import re
import sys
import time
import uuid

from django.conf import settings
from django.urls import resolve
from django.utils import timezone
from drf_api_logger import API_LOGGER_SIGNAL
from drf_api_logger.start_logger_when_server_starts import LOGGER_THREAD
from drf_api_logger.utils import get_client_ip, get_headers, mask_sensitive_data


class APILoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

        self.database = False
        if hasattr(settings, "DRF_API_LOGGER_DATABASE"):
            self.database = settings.DRF_API_LOGGER_DATABASE

        self.signal = False
        if hasattr(settings, "DRF_API_LOGGER_SIGNAL"):
            self.signal = settings.DRF_API_LOGGER_SIGNAL

        self.path_type = "ABSOLUTE"
        if hasattr(settings, "DRF_API_LOGGER_PATH_TYPE"):
            if settings.DRF_API_LOGGER_PATH_TYPE in ["ABSOLUTE", "RAW_URI", "FULL_PATH"]:
                self.path_type = settings.DRF_API_LOGGER_PATH_TYPE

        self.skip_url_name = []
        if hasattr(settings, "DRF_API_LOGGER_SKIP_URL_NAME"):
            if (
                type(settings.DRF_API_LOGGER_SKIP_URL_NAME) is tuple
                or type(settings.DRF_API_LOGGER_SKIP_URL_NAME) is list
            ):
                self.skip_url_name = settings.DRF_API_LOGGER_SKIP_URL_NAME

        self.skip_namespace = []
        if hasattr(settings, "DRF_API_LOGGER_SKIP_NAMESPACE"):
            if (
                type(settings.DRF_API_LOGGER_SKIP_NAMESPACE) is tuple
                or type(settings.DRF_API_LOGGER_SKIP_NAMESPACE) is list
            ):
                self.skip_namespace = settings.DRF_API_LOGGER_SKIP_NAMESPACE

        self.methods = []
        if hasattr(settings, "DRF_API_LOGGER_METHODS"):
            if type(settings.DRF_API_LOGGER_METHODS) is tuple or type(settings.DRF_API_LOGGER_METHODS) is list:
                self.methods = settings.DRF_API_LOGGER_METHODS

        self.status_codes = []
        if hasattr(settings, "DRF_API_LOGGER_STATUS_CODES"):
            if (
                type(settings.DRF_API_LOGGER_STATUS_CODES) is tuple
                or type(settings.DRF_API_LOGGER_STATUS_CODES) is list
            ):
                self.status_codes = settings.DRF_API_LOGGER_STATUS_CODES

        self.enable_tracing = False
        self.tracing_id_header_name = None
        if hasattr(settings, "DRF_API_LOGGER_ENABLE_TRACING"):
            self.enable_tracing = settings.DRF_API_LOGGER_ENABLE_TRACING
            if self.enable_tracing and hasattr(settings, "DRF_API_LOGGER_TRACING_ID_HEADER_NAME"):
                self.tracing_id_header_name = settings.DRF_API_LOGGER_TRACING_ID_HEADER_NAME

        self.tracing_func_name = None
        if hasattr(settings, "DRF_API_LOGGER_TRACING_FUNC"):
            mod_name, func_name = settings.DRF_API_LOGGER_TRACING_FUNC.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            self.tracing_func_name = getattr(mod, func_name)

        self.max_request_body_size = -1
        if hasattr(settings, "DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE"):
            if type(settings.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE) is int:
                self.max_request_body_size = settings.DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE

        self.max_reponse_body_size = -1
        if hasattr(settings, "DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE"):
            if type(settings.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE) is int:
                self.max_reponse_body_size = settings.DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE

    def is_static_or_media_request(self, path):
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")

        return path.startswith(static_url) or path.startswith(media_url)

    def __call__(self, request):
        # Skip logging for static and media files
        if self.is_static_or_media_request(request.path):
            return self.get_response(request)

        # Run only if logger is enabled.
        if self.database or self.signal:

            url_name = resolve(request.path_info).url_name
            namespace = resolve(request.path_info).namespace

            # Always skip Admin panel
            if namespace == "admin":
                return self.get_response(request)

            # Skip for url name
            if url_name in self.skip_url_name:
                return self.get_response(request)

            # Skip entire app using namespace
            if namespace in self.skip_namespace:
                return self.get_response(request)

            # Code to be executed for each request/response after
            # the view is called.

            start_time = time.time()

            headers = get_headers(request=request)
            method = request.method

            request_data = ""
            try:
                request_data = json.loads(request.body) if request.body else ""
                if self.max_request_body_size > -1:
                    if sys.getsizeof(request_data) > self.max_request_body_size:
                        """
                        Ignore the request body if larger then specified.
                        """
                        request_data = ""
            except Exception:
                pass

            tracing_id = None
            if self.enable_tracing:
                if self.tracing_id_header_name:
                    tracing_id = headers.get(self.tracing_id_header_name)
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
            if self.status_codes and response.status_code not in self.status_codes:
                return response

            # Log only registered methods if available.
            if len(self.methods) > 0 and method not in self.methods:
                return response

            self.content_types = [
                "application/json",
                "application/vnd.api+json",
                "application/gzip",
                "application/octet-stream",
                "text/calendar",
            ]
            if hasattr(settings, "DRF_API_LOGGER_CONTENT_TYPES") and type(settings.DRF_API_LOGGER_CONTENT_TYPES) in (
                list,
                tuple,
            ):
                for content_type in settings.DRF_API_LOGGER_CONTENT_TYPES:
                    if re.match(r"^application\/vnd\..+\+json$", content_type):
                        self.content_types.append(content_type)

            if response.get("content-type") in self.content_types:
                if response.get("content-type") == "application/gzip":
                    response_body = "** GZIP Archive **"
                elif response.get("content-type") == "application/octet-stream":
                    response_body = "** Binary File **"
                elif getattr(response, "streaming", False):
                    response_body = "** Streaming **"
                elif response.get("content-type") == "text/calendar":
                    response_body = "** Calendar **"

                else:
                    if type(response.content) is bytes:
                        response_body = json.loads(response.content.decode())
                    else:
                        response_body = json.loads(response.content)
                if self.max_reponse_body_size > -1:
                    if sys.getsizeof(response_body) > self.max_reponse_body_size:
                        response_body = ""
                if self.path_type == "ABSOLUTE":
                    api = request.build_absolute_uri()
                elif self.path_type == "FULL_PATH":
                    api = request.get_full_path()
                elif self.path_type == "RAW_URI":
                    api = request.get_raw_uri()
                else:
                    api = request.build_absolute_uri()

                data = dict(
                    api=mask_sensitive_data(api, mask_api_parameters=True),
                    headers=mask_sensitive_data(headers),
                    body=mask_sensitive_data(request_data),
                    method=method,
                    user=request.user if request.user.is_authenticated else None,
                    username=request.user.username if request.user.is_authenticated else None,
                    client_ip_address=get_client_ip(request),
                    response=mask_sensitive_data(response_body),
                    status_code=response.status_code,
                    execution_time=time.time() - start_time,
                    timestamp=timezone.now(),
                )
                if self.database and LOGGER_THREAD:
                    d = data.copy()
                    d["headers"] = json.dumps(d["headers"], indent=4, ensure_ascii=False) if d.get("headers") else ""
                    if request_data:
                        d["body"] = json.dumps(d["body"], indent=4, ensure_ascii=False) if d.get("body") else ""
                    d["response"] = json.dumps(d["response"], indent=4, ensure_ascii=False) if d.get("response") else ""
                    LOGGER_THREAD.put_log_data(data=d)
                if self.signal:
                    if tracing_id:
                        data.update({"tracing_id": tracing_id})
                    API_LOGGER_SIGNAL.listen(**data)
            else:
                return response
        else:
            response = self.get_response(request)
        return response
