from django.contrib import admin
from django.db.models import Count

from drf_api_logger.utils import database_log_enabled

if database_log_enabled():
    from drf_api_logger.models import APILogsModel


    class APILogsAdmin(admin.ModelAdmin):

        def added_on_time(self, obj):
            return obj.added_on.strftime("%d %b %Y %H:%M:%S")

        added_on_time.admin_order_field = 'added_on'
        added_on_time.short_description = 'Added on'

        list_per_page = 20
        list_display = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time',)
        list_filter = ('added_on', 'status_code', 'method',)
        search_fields = ('body', 'response', 'headers', 'api',)
        readonly_fields = (
            'execution_time', 'client_ip_address', 'api',
            'headers', 'body', 'method', 'response', 'status_code', 'added_on_time',
        )
        exclude = ('added_on',)

        change_list_template = 'charts_change_list.html'
        date_hierarchy = 'added_on'

        def changelist_view(self, request, extra_context=None):
            response = super(APILogsAdmin, self).changelist_view(request, extra_context)
            filtered_query_set = response.context_data["cl"].queryset
            analytics_model = filtered_query_set.values('added_on__date').annotate(total=Count('id')).order_by('total')
            status_code_count_mode = filtered_query_set.values('id').values('status_code').annotate(
                total=Count('id')).order_by('status_code')
            status_code_count_keys = list()
            status_code_count_values = list()
            for item in status_code_count_mode:
                status_code_count_keys.append(item.get('status_code'))
                status_code_count_values.append(item.get('total'))
            extra_context = dict(
                analytics=analytics_model,
                status_code_count_keys=status_code_count_keys,
                status_code_count_values=status_code_count_values
            )
            response.context_data.update(extra_context)
            return response

        def has_add_permission(self, request, obj=None):
            return False

        def has_change_permission(self, request, obj=None):
            return False

        def has_delete_permission(self, request, obj=None):
            return False


    admin.site.register(APILogsModel, APILogsAdmin)
