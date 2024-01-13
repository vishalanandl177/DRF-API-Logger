DRF API Logger
==============

|version| |Downloads| |image1| |Open Source| |Donate|

An API Logger for your Django Rest Framework project.

It logs all the API information for content type “application/json”. 
- URL 
- Request Body 
- Request Headers 
- Request Method 
- API Response
- Status Code 
- API Call Time 
- Server Execution Time 
- Client IP Address

You can log API information into the database or listen to the logger
signals for different use cases, or you can do both.

-  The logger uses a separate thread to run, so it won’t affect your API
   response time.

Installation
------------

Install or add drf-api-logger.

.. code:: python

   pip install drf-api-logger

Add in INSTALLED_APPS

.. code:: python

   INSTALLED_APPS = [
       'django.contrib.admin',
       'django.contrib.auth',
       'django.contrib.contenttypes',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',

       'drf_api_logger',  #  Add here
   ]

Add in MIDDLEWARE

.. code:: python

   MIDDLEWARE = [
       'django.middleware.security.SecurityMiddleware',
       'django.contrib.sessions.middleware.SessionMiddleware',
       'django.middleware.common.CommonMiddleware',
       'django.middleware.csrf.CsrfViewMiddleware',
       'django.contrib.auth.middleware.AuthenticationMiddleware',
       'django.contrib.messages.middleware.MessageMiddleware',
       'django.middleware.clickjacking.XFrameOptionsMiddleware',

       'drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware', # Add here
   ]

\* Add these lines in the Django Rest Framework settings file.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Store logs into the database
----------------------------

Log every request into the database.

.. code:: python

   DRF_API_LOGGER_DATABASE = True  # Default to False

-  Logs will be available in the Django Admin Panel.

-  The search bar will search in Request Body, Response, Headers, and
   API URL.

-  You can also filter the logs based on the “added_on” date, Status
   Code, and Request Methods.

.. figure:: https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/logs.png?raw=true,
   :alt: Logger


.. figure:: https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/graph.png?raw=true,
   :alt: Graph


.. figure:: https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/lists.png?raw=true,
   :alt: Lists


.. figure:: https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/details.png?raw=true,
   :alt: Details


Note: Make sure to migrate. It will create a table for the logger if
“DRF_API_LOGGER_DATABASE” is True else if already exists, it will delete
the table.

To listen for the logger signals.
---------------------------------

Listen to the signal as soon as any API is called. So you can log the
API data into a file or for different use cases.

.. code:: python

   DRF_API_LOGGER_SIGNAL = True  # Default to False

Example code to listen to the API Logger Signal.

.. code:: python

   """
   Import API_LOGGER_SIGNAL
   """
   from drf_api_logger import API_LOGGER_SIGNAL


   """
   Create a function that is going to listen to the API logger signals.
   """
   def listener_one(**kwargs):
       print(kwargs)

   def listener_two(**kwargs):
       print(kwargs)

   """
   It will listen to all the API logs whenever an API is called.
   You can also listen to signals in multiple functions.
   """
   API_LOGGER_SIGNAL.listen += listener_one
   API_LOGGER_SIGNAL.listen += listener_two

   """
   Unsubscribe to signals.
   """

   API_LOGGER_SIGNAL.listen -= listener_one

Queue
~~~~~

DRF API Logger usage queue to hold the logs before inserting them into
the database. Once the queue is full, it bulk inserts into the database.

Specify the queue size.

.. code:: python

   DRF_LOGGER_QUEUE_MAX_SIZE = 50  # Default to 50 if not specified.

Interval
~~~~~~~~

DRF API Logger also waits for a period of time. If the queue is not full
and there are some logs to be inserted, it inserts after the interval
ends.

Specify an interval (In Seconds).

.. code:: python

   DRF_LOGGER_INTERVAL = 10  # In Seconds, Default to 10 seconds if not specified.

Note: The API call time (added_on) is a timezone-aware datetime object.
It is the actual time of the API call irrespective of interval value or
queue size. ### Skip namespace You can skip the entire app to be logged
into the database by specifying the namespace of the app as a list.

.. code:: python

   DRF_API_LOGGER_SKIP_NAMESPACE = ['APP_NAMESPACE1', 'APP_NAMESPACE2']

Skip URL Name
~~~~~~~~~~~~~

You can also skip any API to be logged by using the url_name of the API.

.. code:: python

   DRF_API_LOGGER_SKIP_URL_NAME = ['url_name1', 'url_name2']

Note: It does not log Django Admin Panel API calls.

Hide Sensitive Data From Logs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You may wish to hide sensitive information from being exposed in the
logs. You do this by setting ``DRF_API_LOGGER_EXCLUDE_KEYS`` in
settings.py to a list of your desired sensitive keys. The default is

.. code:: python

   DRF_API_LOGGER_EXCLUDE_KEYS = ['password', 'token', 'access', 'refresh']
   # Sensitive data will be replaced with "***FILTERED***".

Change the default database to store API logs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   DRF_API_LOGGER_DEFAULT_DATABASE = 'default'  # Default to "default" if not specified
   """
   Make sure to migrate the database specified in DRF_API_LOGGER_DEFAULT_DATABASE.
   """

Want to identify slow APIs? (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also identify slow APIs by specifying
``DRF_API_LOGGER_SLOW_API_ABOVE`` in settings.py.

A new filter (By API Performance) will be visible, and you can choose a
slow or fast API.

.. code:: python

   DRF_API_LOGGER_SLOW_API_ABOVE = 200  # Default to None
   # Specify in milli-seconds.

Want to log only selected request methods? (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can log only selected methods by specifying
``DRF_API_LOGGER_METHODS`` in settings.py.

.. code:: python

   DRF_API_LOGGER_METHODS = ['GET', 'POST', 'DELETE', 'PUT']  # Default to an empty list (Log all the requests).

Want to log only selected response status codes? (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can log only selected responses by specifying
``DRF_API_LOGGER_STATUS_CODES`` in settings.py.

.. code:: python

   DRF_API_LOGGER_STATUS_CODES = [200, 400, 404, 500]  # Default to an empty list (Log all responses).

Want to see the API information in the local timezone? (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also change the timezone by specifying
``DRF_API_LOGGER_TIMEDELTA`` in settings.py. It won’t change the
Database timezone. It will remain UTC or the timezone you have defined.

.. code:: python

   DRF_API_LOGGER_TIMEDELTA = 330 # UTC + 330 Minutes = IST (5:Hours, 30:Minutes ahead from UTC)
   # Specify in minutes.

.. code:: python

   # Yoc can specify negative values for the countries behind the UTC timezone.
   DRF_API_LOGGER_TIMEDELTA = -30  # Example

Ignore data based on maximum request or response body? (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Request/Response bodies By default, DRF API LOGGER will save the request
and response bodies for each request for future viewing no matter how
large. If DRF API LOGGER is used in production under heavy volume with
large bodies this can have a huge impact on space/time performance.

This behavior can be configured with the following options additional:

.. code:: python

   # DRF API LOGGER takes anything < 0 as no limit.
   # If response body > 1024 bytes, ignore.
   DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 1024  # default to -1, no limit.
   DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 1024  # default to -1, no limit.

API with or without Host
~~~~~~~~~~~~~~~~~~~~~~~~

You can specify whether an endpoint of API should have absolute URI or
not by setting this variable in the DRF settings.py file.

.. code:: python

   DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'  # Default to ABSOLUTE if not specified
   # Possible values are ABSOLUTE, FULL_PATH or RAW_URI

Tracing
~~~~~~~

You can enable tracing by specifying ``DRF_API_LOGGER_ENABLE_TRACING``
in settings.py. This will add a tracing ID (UUID.uuid4()) in the signals
of the DRF API Logger (if enabled).

In views, you can use request.tracing_id to get the tracing ID.

.. code:: python

   DRF_API_LOGGER_ENABLE_TRACING = True  # default to False

Want to generate your tracing uuid?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, the DRF API Logger uses uuid.uuid4() to generate tracing id.
If you want to use your custom function to generate uuid, specify
DRF_API_LOGGER_TRACING_FUNC in the setting.py file.

.. code:: python

   DRF_API_LOGGER_TRACING_FUNC = 'foo.bar.func_name'

Tracing already present in headers?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the tracing ID is already coming as a part of request headers, you
can specify the header name.

.. code:: python

   DRF_API_LOGGER_TRACING_ID_HEADER_NAME: str = 'X_TRACING_ID'  # Replace with actual header name.

Considering we are accessing the following URL:
http://127.0.0.1:8000/api/v1/?page=123 DRF_API_LOGGER_PATH_TYPE possible
values are: 1. ABSOLUTE (Default) :

::

   Function used ```request.build_absolute_uri()```

   Output: ```http://127.0.0.1:8000/api/v1/?page=123```

2. FULL_PATH

   Function used ``request.get_full_path()``

   Output: ``/api/v1/?page=123``

3. RAW_URI

   Function used ``request.get_raw_uri()``

   Output: ``http://127.0.0.1:8000/api/v1/?page=123``

   Note: Similar to ABSOLUTE but skip allowed hosts protection, so may
   return an insecure URI.

Use the DRF API Logger Model to query
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the DRF API Logger Model to query some information.

Note: Make sure to set “DRF_API_LOGGER_DATABASE = True” in the
settings.py file.

.. code:: python

   from drf_api_logger.models import APILogsModel

   """
   Example:
   Select records for status_code 200.
   """

   result_for_200_status_code = APILogsModel.objects.filter(status_code=200)

DRF API Logger Model:

.. code:: python

   class APILogsModel(Model):
      id = models.BigAutoField(primary_key=True)
      api = models.CharField(max_length=1024, help_text='API URL')
      headers = models.TextField()
      body = models.TextField()
      method = models.CharField(max_length=10, db_index=True)
      client_ip_address = models.CharField(max_length=50)
      response = models.TextField()
      status_code = models.PositiveSmallIntegerField(help_text='Response status code', db_index=True)
      execution_time = models.DecimalField(decimal_places=5, max_digits=8,
                                          help_text='Server execution time (Not complete response time.)')
      added_on = models.DateTimeField()

      def __str__(self):
         return self.api

      class Meta:
         db_table = 'drf_api_logs'
         verbose_name = 'API Log'
         verbose_name_plural = 'API Logs'

Note:
~~~~~

After some time, there will be too much data in the database. Searching
and filtering may get slower. If you want, you can delete or archive the
older data. To improve the searching or filtering, try to add indexes in
the ‘drf_api_logs’ table.

.. |version| image:: https://img.shields.io/badge/version-1.1.15-blue.svg
.. |Downloads| image:: https://static.pepy.tech/personalized-badge/drf-api-logger?period=total&units=none&left_color=black&right_color=orange&left_text=Downloads%20Total
   :target: http://pepy.tech/project/drf-api-logger
.. |image1| image:: https://static.pepy.tech/personalized-badge/drf-api-logger?period=month&units=none&left_color=black&right_color=orange&left_text=Downloads%20Last%20Month
   :target: https://pepy.tech/project/drf-api-logger
.. |Open Source| image:: https://badges.frapsoft.com/os/v1/open-source.svg?v=103
   :target: https://opensource.org/
.. |Donate| image:: https://img.shields.io/badge/$-support-ff69b4.svg?style=flat
   :target: https://paypal.me/chynybekov
