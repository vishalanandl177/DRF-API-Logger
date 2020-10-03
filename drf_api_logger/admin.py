from django.contrib import admin

from drf_api_logger.utils import database_log_enabled

if database_log_enabled():
    from drf_api_logger.models import APILogsModel


    class APILogsAdmin(admin.ModelAdmin):

        def added_on_time(self, obj):
            return obj.added_on.strftime("%d %b %Y %H:%M:%S")

        added_on_time.admin_order_field = 'added_on'
        added_on_time.short_description = 'Time'

        list_per_page = 20
        list_display = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time',)
        list_filter = ('added_on', 'status_code', 'method',)
        search_fields = ('body', 'response', 'headers', 'api',)
        readonly_fields = (
            'execution_time', 'client_ip_address', 'api',
            'headers', 'body', 'method', 'response', 'status_code', 'added_on_time',
        )

        def has_add_permission(self, request, obj=None):
            return False

        def has_change_permission(self, request, obj=None):
            return False


    admin.site.register(APILogsModel, APILogsAdmin)
