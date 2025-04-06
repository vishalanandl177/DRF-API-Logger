from django.db import models
from drf_api_logger.utils import database_log_enabled

# Only define and load the models if database logging is enabled in settings.
if database_log_enabled():
    """
    Load models conditionally based on `DRF_API_LOGGER_DATABASE` setting.
    This avoids unnecessary model registration/migrations when DB logging is disabled.
    """


    class BaseModel(models.Model):
        """
        Abstract base model that provides common fields and behavior
        for all logging-related models.

        Fields:
        -------
        - id: Primary key using BigAutoField for better scalability.
        - added_on: Timestamp of when the log entry was created.
        """

        id = models.BigAutoField(primary_key=True)
        added_on = models.DateTimeField()

        def __str__(self):
            """
            Return the string representation of the instance,
            which is the ID in this base model.
            """
            return str(self.id)

        class Meta:
            abstract = True  # This model will not be created as a DB table.
            ordering = ('-added_on',)  # Default ordering: newest logs first.


    class APILogsModel(BaseModel):
        """
        Model to store detailed logs of API requests and responses.
        This includes metadata such as headers, request body, response, etc.

        Inherits from BaseModel to include `id` and `added_on` fields.

        Fields:
        -------
        - api: The URL of the API that was accessed.
        - headers: HTTP headers from the request.
        - body: Body of the request.
        - method: HTTP method used (GET, POST, etc.), indexed for performance.
        - client_ip_address: The IP address of the client making the request.
        - response: Response content sent back to the client.
        - status_code: HTTP response status code, indexed for filtering/searching.
        - execution_time: Time taken by the server to process the request, excluding network latency.
        """

        api = models.CharField(
            max_length=1024,
            help_text='API URL'
        )
        headers = models.TextField()
        body = models.TextField()
        method = models.CharField(
            max_length=10,
            db_index=True  # Speeds up queries filtering by method (e.g., GET/POST).
        )
        client_ip_address = models.CharField(
            max_length=50
        )
        response = models.TextField()
        status_code = models.PositiveSmallIntegerField(
            help_text='Response status code',
            db_index=True  # Useful for filtering by success/error status
        )
        execution_time = models.DecimalField(
            decimal_places=5,
            max_digits=8,
            help_text='Server execution time (Not complete response time.)'
        )

        def __str__(self):
            """
            Returns a readable representation of the log entry,
            which is the accessed API endpoint.
            """
            return self.api

        class Meta:
            db_table = 'drf_api_logs'  # Custom DB table name for better control
            verbose_name = 'API Log'  # Human-readable name for Django admin
            verbose_name_plural = 'API Logs'  # Plural name for admin listing
