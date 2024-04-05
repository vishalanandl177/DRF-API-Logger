from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from drf_api_logger.utils import database_log_enabled


if database_log_enabled():
    """
    Load models only if DRF_API_LOGGER_DATABASE is True
    """
    class BaseModel(models.Model):
        id = models.BigAutoField(primary_key=True)

        timestamp = models.DateTimeField(verbose_name=_('Timestamp'), auto_now_add=True)

        def __str__(self):
            return str(self.id)

        class Meta:
            abstract = True
            ordering = ('-timestamp',)


    class APILogs(BaseModel):
        api = models.CharField(max_length=1024, verbose_name=_('API URL'), db_index=True)
        user = models.ForeignKey(User, verbose_name=_('User'), db_index=True, on_delete=models.DO_NOTHING, null=True)
        username = models.CharField(max_length=255, verbose_name=_('User name'), null=True, db_index=True)
        headers = models.TextField(verbose_name=_('Request headers'))
        body = models.TextField(verbose_name=_('Request body'))
        method = models.CharField(max_length=10, db_index=True, verbose_name=_('Request method'))
        client_ip_address = models.CharField(max_length=50, verbose_name=_('Client IP'))
        response = models.TextField(verbose_name=_('Response'))
        status_code = models.PositiveSmallIntegerField(db_index=True, verbose_name=_('Status code'))
        execution_time = models.DecimalField(decimal_places=5, max_digits=8,
                                             help_text=_('Server execution time (Not complete response time.)'),
                                             verbose_name=_('Execution time'))

        def __str__(self):
            return self.api

        class Meta:
            db_table = 'drf_api_logs'
            verbose_name = 'API Log'
            verbose_name_plural = 'API Logs'
