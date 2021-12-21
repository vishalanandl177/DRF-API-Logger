# DRF API Logger
![version](https://img.shields.io/badge/version-1.0.9-blue.svg)
[![Downloads](https://static.pepy.tech/personalized-badge/drf-api-logger?period=total&units=none&left_color=black&right_color=orange&left_text=Downloads%20Total)](http://pepy.tech/project/drf-api-logger)
[![Downloads](https://static.pepy.tech/personalized-badge/drf-api-logger?period=month&units=none&left_color=black&right_color=orange&left_text=Downloads%20Last%20Month)](https://pepy.tech/project/drf-api-logger)
[![Downloads](https://static.pepy.tech/personalized-badge/drf-api-logger?period=week&units=none&left_color=black&right_color=orange&left_text=Downloads%20Last%20Week)](https://pepy.tech/project/drf-api-logger)
[![Open Source](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://opensource.org/)
[![Donate](https://img.shields.io/badge/$-support-ff69b4.svg?style=flat)](https://paypal.me/chynybekov)  

<a href="https://discord.gg/Kr8SbgPe"><img src="https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white" alt="Join Community Badge"/></a>
<a href="https://www.instagram.com/coderssecret/"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Join Instagram"/></a>
<a href="https://github.com/vishalanandl177"><img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/></a>



An API Logger for your Django Rest Framework project.

It logs all the API information for content type "application/json".
1. URL
2. Request Body
3. Request Headers
4. Request Method
5. API Response
6. Status Code
7. API Call Time
8. Server Execution Time
9. Client IP Address


You can log API information into the database or listen to the logger signals for different use-cases, or you can do both.

* The logger usage a separate thread to run, so it won't affect your API response time.

## Installation

Install or add drf-api-logger.
```shell script
pip install drf-api-logger
```

Add in INSTALLED_APPS
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'drf_api_logger',  #  Add here
]
```

Add in MIDDLEWARE
```python
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
```


#### * Add these lines in Django Rest Framework settings file.

## Store logs into the database
Log every request into the database.
```python
DRF_API_LOGGER_DATABASE = True  # Default to False
```
* Logs will be available in Django Admin Panel.

* The search bar will search in Request Body, Response, Headers and API URL.

* You can also filter the logs based on the "added_on" date, Status Code and Request Methods.

![Alt text](https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/logs.png?raw=true, "Logger")

![Alt text](https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/graph.png?raw=true, "Graph")

![Alt text](https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/lists.png?raw=true, "Lists")

![Alt text](https://raw.githubusercontent.com/vishalanandl177/DRF-API-Logger/master/details.png?raw=true, "Details")

Note: Make sure to migrate. It will create a table for logger if "DRF_API_LOGGER_DATABASE" is True else if already exists, it will delete the table.

## To listen for the logger signals.
Listen to the signal as soon as any API is called. So you can log the API data into a file or for different use-cases.
```python
DRF_API_LOGGER_SIGNAL = True  # Default to False
```
Example code to listen to the API Logger Signal.
```python
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
You can also listen signals in multiple functions.
"""
API_LOGGER_SIGNAL.listen += listener_one
API_LOGGER_SIGNAL.listen += listener_two

"""
Unsubscribe to signals.
"""

API_LOGGER_SIGNAL.listen -= listener_one
```

### Queue

DRF API Logger usage queue to hold the logs before inserting into the database. Once queue is full, it bulk inserts into the database.

Specify the queue size.
```python
DRF_LOGGER_QUEUE_MAX_SIZE = 50  # Default to 50 if not specified.
```

### Interval

DRF API Logger also waits for a period of time. If queue is not full and there are some logs to be inserted, it inserts after interval ends.

Specify an interval (In Seconds).
```python
DRF_LOGGER_INTERVAL = 10  # In Seconds, Default to 10 seconds if not specified.
```
Note: The API call time (added_on) is a timezone aware datetime object. It is actual time of API call irrespective of interval value or queue size.
### Skip namespace
You can skip the entire app to be logged into the database by specifying namespace of the app as list.
```python
DRF_API_LOGGER_SKIP_NAMESPACE = ['APP_NAMESPACE1', 'APP_NAMESPACE2']
```

### Skip URL Name
You can also skip any API to be logged by using url_name of the API.
```python
DRF_API_LOGGER_SKIP_URL_NAME = ['url_name1', 'url_name2']
```

Note: It does not log Django Admin Panel API calls.

### Hide Sensitive Data From Logs
You may wish to hide sensitive information from being exposed in the logs. 
You do this by setting `DRF_API_LOGGER_EXCLUDE_KEYS` in settings.py to a list of your desired sensitive keys. 
The default is
```python
DRF_API_LOGGER_EXCLUDE_KEYS = ['password', 'token', 'access', 'refresh']
# Sensitive data will be replaced with "***FILTERED***".
```

### Change default database to store API logs
```python
DRF_API_LOGGER_DEFAULT_DATABASE = 'default'  # Default to "default" if not specified
"""
Make sure to migrate the database specified in DRF_API_LOGGER_DEFAULT_DATABASE.
"""
```

### Want to identify slow APIs? (Optional)
You can also identify slow APIs by specifying `DRF_API_LOGGER_SLOW_API_ABOVE` in settings.py.

A new filter (By API Performance) will be visible, and you can choose slow or fast API.
```python
DRF_API_LOGGER_SLOW_API_ABOVE = 200  # Default to None
# Specify in milli-seconds.
```

### Want to see the API information in local timezone? (Optional)
You can also identify slow APIs by specifying `DRF_API_LOGGER_TIMEDELTA` in settings.py.
It is going to display the API request time after adding the timedelta specified in the settings.py file.
It won't change the Database timezone.
```python
DRF_API_LOGGER_TIMEDELTA = 330 # UTC + 330 Minutes = IST (5:Hours, 30:Minutes ahead from UTC) 
# Specify in minutes.
```
```python
# Yoc can specify negative values for the countries behind the UTC timezone.
DRF_API_LOGGER_TIMEDELTA = -30  # Example
```

### API with or without Host
You can specify an endpoint of API should have absolute URI or not by setting this variable in DRF settings.py file.
```python
DRF_API_LOGGER_PATH_TYPE = 'ABSOLUTE'  # Default to ABSOLUTE if not specified
# Possible values are ABSOLUTE, FULL_PATH or RAW_URI
```

Considering we are accessing the following URL: http://127.0.0.1:8000/api/v1/?page=123
DRF_API_LOGGER_PATH_TYPE possible values are:
1. ABSOLUTE (Default) :   

    Function used ```request.build_absolute_uri()```
    
    Output: ```http://127.0.0.1:8000/api/v1/?page=123```
    
2. FULL_PATH

    Function used ```request.get_full_path()```
    
    Output: ```/api/v1/?page=123```
    
3. RAW_URI

    Function used ```request.get_raw_uri()```
    
    Output: ```http://127.0.0.1:8000/api/v1/?page=123```
    
    Note: Similar to ABSOLUTE but skip allowed hosts protection, so may return an insecure URI.


### Use DRF API Logger Model to query 
You can use the DRF API Logger Model to query some information.

Note: Make sure to set "DRF_API_LOGGER_DATABASE = True" in settings.py file.
```
from drf_api_logger.models import APILogsModel

"""
Example:
Select records for status_code 200.
"""
result_for_200_status_code = APILogsModel.objects.filter(status_code=200)
```

DRF API Logger Model:
```
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

```

### Note:
After sometime, there will be too many data in the database. Searching and filter may get slower.
If you want, you can delete or archive the older data.
To improve the searching or filtering, try to add indexes in the 'drf_api_logs' table.

