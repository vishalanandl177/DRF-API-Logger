from datetime import timedelta
from django.conf import settings
from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from drf_api_logger.utils import database_log_enabled

# Ensure the API log model and related features are only used if enabled in settings
if database_log_enabled():
    from drf_api_logger.models import APILogsModel
    from django.utils.translation import gettext_lazy as _
    import csv

    class ExportCsvMixin:
        """
        Mixin class to enable exporting selected queryset to CSV in Django admin.
        """

        def export_as_csv(self, request, queryset):
            """
            Export selected objects as a CSV file.
            """
            meta = self.model._meta
            field_names = [field.name for field in meta.fields]

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename={meta}.csv'
            writer = csv.writer(response)

            # Write headers
            writer.writerow(field_names)
            # Write rows
            for obj in queryset:
                writer.writerow([getattr(obj, field) for field in field_names])

            return response

        export_as_csv.short_description = "Export Selected"


    class SlowAPIsFilter(admin.SimpleListFilter):
        """
        Custom filter for Django admin to categorize API logs as 'slow' or 'fast'
        based on execution time threshold.
        """

        title = _('API Performance')
        parameter_name = 'api_performance'

        def __init__(self, request, params, model, model_admin):
            super().__init__(request, params, model, model_admin)
            # Load and convert the slow API threshold setting from milliseconds to seconds
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                if isinstance(settings.DRF_API_LOGGER_SLOW_API_ABOVE, int):
                    self._DRF_API_LOGGER_SLOW_API_ABOVE = settings.DRF_API_LOGGER_SLOW_API_ABOVE / 1000

        def lookups(self, request, model_admin):
            """
            Returns lookup options for the filter in the admin sidebar.
            """
            slow = 'Slow'
            fast = 'Fast'
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                slow += f', >={settings.DRF_API_LOGGER_SLOW_API_ABOVE}ms'
                fast += f', <{settings.DRF_API_LOGGER_SLOW_API_ABOVE}ms'
            return (
                ('slow', _(slow)),
                ('fast', _(fast)),
            )

        def queryset(self, request, queryset):
            """
            Returns filtered queryset depending on whether 'slow' or 'fast'
            option is selected in the filter.
            """
            if self.value() == 'slow':
                return queryset.filter(execution_time__gte=self._DRF_API_LOGGER_SLOW_API_ABOVE)
            if self.value() == 'fast':
                return queryset.filter(execution_time__lt=self._DRF_API_LOGGER_SLOW_API_ABOVE)
            return queryset


    class APILogsAdmin(admin.ModelAdmin, ExportCsvMixin):
        """
        Custom admin class for the API logs model with filters, charts, export functionality,
        and restricted permissions.
        """

        actions = ["export_as_csv"]

        def __init__(self, model, admin_site):
            super().__init__(model, admin_site)

            self._DRF_API_LOGGER_TIMEDELTA = 0

            # Conditionally add the slow API filter if setting is provided
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                if isinstance(settings.DRF_API_LOGGER_SLOW_API_ABOVE, int):
                    self.list_filter += (SlowAPIsFilter,)

            # Time delta used for adjusting timestamp display
            if hasattr(settings, 'DRF_API_LOGGER_TIMEDELTA'):
                if isinstance(settings.DRF_API_LOGGER_TIMEDELTA, int):
                    self._DRF_API_LOGGER_TIMEDELTA = settings.DRF_API_LOGGER_TIMEDELTA

        def added_on_time(self, obj):
            """
            Returns formatted 'added_on' timestamp adjusted by timedelta setting.
            """
            return (obj.added_on + timedelta(minutes=self._DRF_API_LOGGER_TIMEDELTA)).strftime("%d %b %Y %H:%M:%S")

        added_on_time.admin_order_field = 'added_on'
        added_on_time.short_description = 'Added on'

        # Admin UI settings
        list_per_page = 20
        list_display = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time',)
        list_filter = ('added_on', 'status_code', 'method',)
        search_fields = ('body', 'response', 'headers', 'api',)
        readonly_fields = (
            'execution_time', 'client_ip_address', 'api',
            'headers', 'body', 'method', 'response', 'status_code', 'added_on_time',
        )
        exclude = ('added_on',)

        # Custom admin templates
        change_list_template = 'charts_change_list.html'
        change_form_template = 'change_form.html'
        date_hierarchy = 'added_on'

        def changelist_view(self, request, extra_context=None):
            """
            Override to inject custom chart data for status codes and analytics into the context.
            """
            response = super(APILogsAdmin, self).changelist_view(request, extra_context)
            try:
                filtered_query_set = response.context_data["cl"].queryset
            except Exception:
                return response

            # Aggregate logs by date
            analytics_model = filtered_query_set.values('added_on__date').annotate(
                total=Count('id')
            ).order_by('total')

            # Count each unique status code
            status_code_count_mode = filtered_query_set.values('id').values('status_code').annotate(
                total=Count('id')).order_by('status_code')

            status_code_count_keys = [item.get('status_code') for item in status_code_count_mode]
            status_code_count_values = [item.get('total') for item in status_code_count_mode]

            # Add chart data to context
            extra_context = dict(
                analytics=analytics_model,
                status_code_count_keys=status_code_count_keys,
                status_code_count_values=status_code_count_values
            )

            response.context_data.update(extra_context)
            return response

        def get_queryset(self, request):
            """
            Ensure the queryset uses the correct database as configured in settings.
            """
            drf_api_logger_default_database = 'default'
            if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
                drf_api_logger_default_database = settings.DRF_API_LOGGER_DEFAULT_DATABASE
            return super(APILogsAdmin, self).get_queryset(request).using(drf_api_logger_default_database)

        def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
            """
            If `export` is in the query parameters, return CSV export of a single object.
            """
            if request.GET.get('export', False):
                drf_api_logger_default_database = 'default'
                if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
                    drf_api_logger_default_database = settings.DRF_API_LOGGER_DEFAULT_DATABASE

                export_queryset = self.get_queryset(request).filter(pk=object_id).using(drf_api_logger_default_database)
                return self.export_as_csv(request, export_queryset)

            return super(APILogsAdmin, self).changeform_view(request, object_id, form_url, extra_context)

        def has_add_permission(self, request, obj=None):
            """
            Prevent adding logs from the admin.
            """
            return False

        def has_change_permission(self, request, obj=None):
            """
            Prevent modifying logs from the admin.
            """
            return False

    # Register the model with the custom admin class
    admin.site.register(APILogsModel, APILogsAdmin)
