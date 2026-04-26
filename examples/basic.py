"""
Basic Setup — Get logging in 2 minutes.

Add this to your Django settings.py.
"""

# --- Add to INSTALLED_APPS ---
INSTALLED_APPS = [
    # ... your other apps
    'drf_api_logger',
]

# --- Add to MIDDLEWARE ---
MIDDLEWARE = [
    # ... your other middleware
    'drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware',
]

# --- Enable database logging ---
DRF_API_LOGGER_DATABASE = True

# --- Run migrations ---
# python manage.py migrate

# That's it. Every API request is now logged with:
# - URL, method, headers, body
# - Response body and status code
# - Execution time
# - Client IP address
# - Sensitive data automatically masked (password, token, access, refresh)
#
# View logs in Django Admin at /admin/ under "DRF API Logger > API Logs".
