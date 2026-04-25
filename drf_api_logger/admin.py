import json
from datetime import timedelta
from django.conf import settings
from django.contrib import admin
from django.db.models import Count, Avg
from django.http import HttpResponse
from django.utils.html import format_html
from drf_api_logger.utils import database_log_enabled


def _get_profiling_diagnosis(profiling):
    """Generate a diagnosis hint based on profiling data patterns."""
    total = profiling.get('view_and_serialization', 0)
    sql = profiling.get('sql', {})
    sql_time = sql.get('total_time', 0)
    query_count = sql.get('query_count', 0)

    if total <= 0:
        return None

    sql_pct = (sql_time / total) * 100 if total > 0 else 0

    if sql_pct > 70 and query_count >= 10:
        return 'N+1 query problem likely. {}% of time in SQL with {} queries.'.format(
            int(sql_pct), query_count
        )
    if sql_pct > 70 and query_count < 5:
        return 'Few but slow queries ({}). Check indexes and query plans.'.format(query_count)
    if sql_pct < 20 and total > 0.5:
        return 'Bottleneck is in business logic or external calls. SQL is only {}% of time.'.format(
            int(sql_pct)
        )
    middleware_before = profiling.get('middleware_before_view', 0)
    middleware_after = profiling.get('middleware_after_view', 0)
    middleware_total = middleware_before + middleware_after
    if total > 0 and (middleware_total / total) > 0.1:
        return 'Middleware overhead is unusually high ({:.1f}% of total).'.format(
            (middleware_total / total) * 100
        )
    return None


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


    class HighQueryCountFilter(admin.SimpleListFilter):
        title = _('SQL Query Volume')
        parameter_name = 'sql_queries'

        def lookups(self, request, model_admin):
            return (
                ('high', _('High (>= 10 queries)')),
                ('moderate', _('Moderate (5-9)')),
                ('low', _('Low (< 5)')),
                ('none', _('No profiling data')),
            )

        def queryset(self, request, queryset):
            if self.value() == 'high':
                return queryset.filter(sql_query_count__gte=10)
            if self.value() == 'moderate':
                return queryset.filter(sql_query_count__gte=5, sql_query_count__lt=10)
            if self.value() == 'low':
                return queryset.filter(sql_query_count__lt=5, sql_query_count__isnull=False)
            if self.value() == 'none':
                return queryset.filter(sql_query_count__isnull=True)
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
            self._DRF_API_LOGGER_ENABLE_PROFILING = False

            # Conditionally add the slow API filter if setting is provided
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                if isinstance(settings.DRF_API_LOGGER_SLOW_API_ABOVE, int):
                    self.list_filter += (SlowAPIsFilter,)

            # Time delta used for adjusting timestamp display
            if hasattr(settings, 'DRF_API_LOGGER_TIMEDELTA'):
                if isinstance(settings.DRF_API_LOGGER_TIMEDELTA, int):
                    self._DRF_API_LOGGER_TIMEDELTA = settings.DRF_API_LOGGER_TIMEDELTA

            # Profiling admin enhancements
            if hasattr(settings, 'DRF_API_LOGGER_ENABLE_PROFILING'):
                if settings.DRF_API_LOGGER_ENABLE_PROFILING:
                    self._DRF_API_LOGGER_ENABLE_PROFILING = True
                    self.list_display = (
                        'id', 'api', 'method', 'status_code',
                        'execution_time', 'sql_query_count', 'added_on_time',
                    )
                    self.list_filter += (HighQueryCountFilter,)
                    self.readonly_fields = (
                        'execution_time', 'client_ip_address', 'api',
                        'headers', 'body', 'method', 'response', 'status_code',
                        'added_on_time', 'profiling_breakdown',
                    )

        def added_on_time(self, obj):
            """
            Returns formatted 'added_on' timestamp adjusted by timedelta setting.
            """
            return (obj.added_on + timedelta(minutes=self._DRF_API_LOGGER_TIMEDELTA)).strftime("%d %b %Y %H:%M:%S")

        added_on_time.admin_order_field = 'added_on'
        added_on_time.short_description = 'Added on'

        def profiling_breakdown(self, obj):
            if not obj.profiling_data:
                return '-'
            try:
                data = json.loads(obj.profiling_data)
            except (json.JSONDecodeError, TypeError):
                return '-'

            total = data.get('view_and_serialization', 0)
            sql = data.get('sql', {})
            sql_time = sql.get('total_time', 0)
            query_count = sql.get('query_count', 0)
            mw_before = data.get('middleware_before_view', 0)
            mw_after = data.get('middleware_after_view', 0)
            non_sql = max(total - sql_time, 0)

            def pct(val, denom):
                return '{:.1f}%'.format((val / denom) * 100) if denom > 0 else '-'

            exec_total = mw_before + total + mw_after

            rows = [
                ('Middleware (before view)', '{:.5f}s'.format(mw_before), pct(mw_before, exec_total)),
                ('View + Serialization', '{:.5f}s'.format(total), pct(total, exec_total)),
                ('Middleware (after view)', '{:.5f}s'.format(mw_after), pct(mw_after, exec_total)),
            ]

            sql_rows = []
            if sql:
                sql_rows = [
                    ('SQL Total Time', '{:.5f}s'.format(sql_time), pct(sql_time, exec_total)),
                    ('SQL Query Count', str(query_count), ''),
                    ('Non-SQL (business logic)', '{:.5f}s'.format(non_sql), pct(non_sql, exec_total)),
                ]
                if query_count > 0:
                    avg_per_query = sql_time / query_count
                    sql_rows.append(('Avg per Query', '{:.5f}s'.format(avg_per_query), ''))

            diagnosis = _get_profiling_diagnosis(data)

            html = '<table style="border-collapse:collapse;min-width:400px;">'
            html += '<tr style="background:#f0f0f0;"><th style="padding:6px 12px;text-align:left;">Stage</th>'
            html += '<th style="padding:6px 12px;text-align:right;">Time</th>'
            html += '<th style="padding:6px 12px;text-align:right;">% of Total</th></tr>'

            for label, val, p in rows:
                html += '<tr><td style="padding:4px 12px;">{}</td>'.format(label)
                html += '<td style="padding:4px 12px;text-align:right;font-family:monospace;">{}</td>'.format(val)
                html += '<td style="padding:4px 12px;text-align:right;">{}</td></tr>'.format(p)

            html += '<tr><td colspan="3" style="padding:4px 12px;"><strong>Total: {:.5f}s</strong></td></tr>'.format(exec_total)

            if sql_rows:
                html += '<tr><td colspan="3" style="padding:8px 12px 4px;border-top:1px solid #ccc;">'
                html += '<strong>SQL Breakdown</strong></td></tr>'
                for label, val, p in sql_rows:
                    html += '<tr><td style="padding:4px 12px;">{}</td>'.format(label)
                    html += '<td style="padding:4px 12px;text-align:right;font-family:monospace;">{}</td>'.format(val)
                    html += '<td style="padding:4px 12px;text-align:right;">{}</td></tr>'.format(p)

            if diagnosis:
                html += '<tr><td colspan="3" style="padding:8px 12px;border-top:1px solid #ccc;'
                html += 'background:#fff3cd;color:#856404;">'
                html += '<strong>Diagnosis:</strong> {}</td></tr>'.format(diagnosis)

            html += '</table>'
            return format_html(html)

        profiling_breakdown.short_description = 'Profiling Breakdown'

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

            # Add profiling chart data when profiling is enabled
            if self._DRF_API_LOGGER_ENABLE_PROFILING:
                profiled_qs = filtered_query_set.filter(sql_query_count__isnull=False)
                sql_distribution = profiled_qs.values('added_on__date').annotate(
                    avg_queries=Avg('sql_query_count')
                ).order_by('added_on__date')
                extra_context['sql_distribution'] = list(sql_distribution)
                extra_context['profiling_enabled'] = True

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
            return False

        def has_change_permission(self, request, obj=None):
            return False

    # Register the model with the custom admin class
    admin.site.register(APILogsModel, APILogsAdmin)
