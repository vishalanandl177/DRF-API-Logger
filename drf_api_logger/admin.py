import json
from datetime import timedelta
from django.conf import settings
from django.contrib import admin
from django.db.models import Count, Avg
from django.http import HttpResponse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from drf_api_logger.utils import database_log_enabled


def _prettify_json_field(value):
    """
    Render a stored log field (headers / body / response) as a pretty-printed,
    HTML-escaped JSON block for the admin change form.

    The middleware already stores these as indented JSON, but plain/large or
    non-JSON payloads (truncation markers, XML, streaming placeholders, ...) are
    handled gracefully. The returned markup is wrapped in ``<pre class="apilogs-json">``
    which the change-form template syntax-highlights on the client side. No size
    limit is applied here so even large bodies are prettified in full.
    """
    if value is None or value == '':
        return mark_safe('<div class="apilogs-empty">— empty —</div>')

    text = value if isinstance(value, str) else str(value)
    stripped = text.strip()

    # Special placeholders emitted by the middleware, e.g.
    # "** Response body truncated: 70000 bytes exceeds 65536 byte limit **".
    is_marker = stripped.startswith('**') and stripped.endswith('**')

    badge = ''
    if is_marker and 'truncated' in stripped.lower():
        badge = '<div class="apilogs-truncated">TRUNCATED</div>'

    pretty = text
    if not is_marker:
        try:
            pretty = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except (ValueError, TypeError):
            pretty = text  # leave non-JSON payloads (XML, plain text, ...) as-is

    return mark_safe('{}<pre class="apilogs-json">{}</pre>'.format(badge, escape(pretty)))


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
                        'headers_prettified', 'body_prettified', 'method', 'response_prettified',
                        'status_code', 'added_on_time', 'profiling_breakdown',
                    )
                    self.exclude = (
                        'added_on', 'profiling_data', 'sql_query_count',
                        'headers', 'body', 'response',
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

            view_time = data.get('view_and_serialization', 0)
            sql = data.get('sql', {})
            sql_time = sql.get('total_time', 0)
            query_count = sql.get('query_count', 0)
            mw_before = data.get('middleware_before_view', 0)
            mw_after = data.get('middleware_after_view', 0)
            non_sql = max(view_time - sql_time, 0)
            exec_total = mw_before + view_time + mw_after

            def pct_val(val):
                return (val / exec_total) * 100 if exec_total > 0 else 0

            def bar_color(pct):
                if pct > 70:
                    return '#dc3545'
                if pct > 30:
                    return '#ffc107'
                return '#28a745'

            def render_bar(pct):
                color = bar_color(pct)
                w = max(pct, 1)
                return (
                    '<div class="prof-bar-bg">'
                    '<div style="background:{};border-radius:4px;height:18px;width:{}%;min-width:2px;"></div>'
                    '</div>'
                ).format(color, w)

            diagnosis = _get_profiling_diagnosis(data)

            css = (
                '<style>'
                '.prof-wrap{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:680px;}'
                '.prof-card{border:1px solid var(--hairline-color,#dee2e6);border-radius:8px;overflow:hidden;margin-bottom:16px;}'
                '.prof-header{padding:10px 16px;font-weight:600;font-size:14px;border-bottom:1px solid var(--hairline-color,#dee2e6);}'
                '.prof-header-timing{background:var(--darkened-bg,#e8f4fd);color:var(--header-link-color,#0c5a97);}'
                '.prof-header-sql{background:var(--darkened-bg,#fff8e1);color:var(--header-link-color,#856404);}'
                '.prof-table{width:100%;border-collapse:collapse;}'
                '.prof-table td{padding:8px 16px;border-bottom:1px solid var(--hairline-color,#f0f0f0);font-size:13px;}'
                '.prof-table tr:last-child td{border-bottom:none;}'
                '.prof-label{color:var(--body-quiet-color,#495057);}'
                '.prof-val{font-family:SFMono-Regular,Menlo,Monaco,Consolas,monospace;text-align:right;white-space:nowrap;color:var(--body-fg,#212529);font-weight:500;}'
                '.prof-pct{text-align:right;color:var(--body-quiet-color,#6c757d);font-size:12px;white-space:nowrap;}'
                '.prof-bar{text-align:left;width:140px;}'
                '.prof-bar-bg{background:var(--hairline-color,#e9ecef);border-radius:4px;height:18px;width:120px;display:inline-block;vertical-align:middle;}'
                '.prof-total td{font-weight:700;background:var(--darkened-bg,#f8f9fa);font-size:14px;border-top:2px solid var(--hairline-color,#dee2e6);color:var(--body-fg,#212529);}'
                '.prof-diag{padding:12px 16px;border-radius:8px;margin-top:8px;font-size:13px;}'
                '.prof-diag-warn{background:rgba(255,193,7,0.15);border:1px solid #ffc107;color:#ffc107;}'
                '.prof-diag-ok{background:rgba(40,167,69,0.15);border:1px solid #28a745;color:#28a745;}'
                '.prof-summary{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;}'
                '.prof-stat{border:1px solid var(--hairline-color,#dee2e6);border-radius:8px;padding:12px 20px;text-align:center;min-width:100px;background:var(--darkened-bg,#f8f9fa);}'
                '.prof-stat-val{font-size:22px;font-weight:700;font-family:monospace;}'
                '.prof-stat-label{font-size:11px;color:var(--body-quiet-color,#6c757d);text-transform:uppercase;letter-spacing:0.5px;margin-top:2px;}'
                '</style>'
            )

            exec_ms = exec_total * 1000
            stat_color = '#28a745' if exec_ms < 200 else ('#ffc107' if exec_ms < 1000 else '#dc3545')
            qcount_color = '#28a745' if query_count < 5 else ('#ffc107' if query_count < 10 else '#dc3545')

            html = css
            html += '<div class="prof-wrap">'

            html += '<div class="prof-summary">'
            html += '<div class="prof-stat"><div class="prof-stat-val" style="color:{};">{:.1f}ms</div><div class="prof-stat-label">Total Time</div></div>'.format(stat_color, exec_ms)
            if sql:
                html += '<div class="prof-stat"><div class="prof-stat-val" style="color:{};">{}</div><div class="prof-stat-label">SQL Queries</div></div>'.format(qcount_color, query_count)
                sql_ms = sql_time * 1000
                html += '<div class="prof-stat"><div class="prof-stat-val">{:.1f}ms</div><div class="prof-stat-label">SQL Time</div></div>'.format(sql_ms)
                non_sql_ms = non_sql * 1000
                html += '<div class="prof-stat"><div class="prof-stat-val">{:.1f}ms</div><div class="prof-stat-label">App Logic</div></div>'.format(non_sql_ms)
            html += '</div>'

            timing_rows = [
                ('Middleware (before view)', mw_before),
                ('View + Serialization', view_time),
                ('Middleware (after view)', mw_after),
            ]
            html += '<div class="prof-card">'
            html += '<div class="prof-header prof-header-timing">Timing Breakdown</div>'
            html += '<table class="prof-table">'
            for label, val in timing_rows:
                p = pct_val(val)
                html += '<tr>'
                html += '<td class="prof-label">{}</td>'.format(label)
                html += '<td class="prof-val">{:.3f}ms</td>'.format(val * 1000)
                html += '<td class="prof-pct">{:.1f}%</td>'.format(p)
                html += '<td class="prof-bar">{}</td>'.format(render_bar(p))
                html += '</tr>'
            html += '<tr class="prof-total"><td>Total</td><td class="prof-val">{:.3f}ms</td><td></td><td></td></tr>'.format(exec_ms)
            html += '</table></div>'

            if sql:
                sql_pct = pct_val(sql_time)
                non_sql_pct = pct_val(non_sql)
                html += '<div class="prof-card">'
                html += '<div class="prof-header prof-header-sql">SQL Breakdown</div>'
                html += '<table class="prof-table">'
                html += '<tr><td class="prof-label">SQL Time</td><td class="prof-val">{:.3f}ms</td><td class="prof-pct">{:.1f}%</td><td class="prof-bar">{}</td></tr>'.format(sql_time * 1000, sql_pct, render_bar(sql_pct))
                html += '<tr><td class="prof-label">App Logic (non-SQL)</td><td class="prof-val">{:.3f}ms</td><td class="prof-pct">{:.1f}%</td><td class="prof-bar">{}</td></tr>'.format(non_sql * 1000, non_sql_pct, render_bar(non_sql_pct))
                html += '<tr><td class="prof-label">Query Count</td><td class="prof-val">{}</td><td></td><td></td></tr>'.format(query_count)
                if query_count > 0:
                    html += '<tr><td class="prof-label">Avg per Query</td><td class="prof-val">{:.3f}ms</td><td></td><td></td></tr>'.format((sql_time / query_count) * 1000)
                html += '</table></div>'

            if diagnosis:
                html += '<div class="prof-diag prof-diag-warn"><strong>Diagnosis:</strong> {}</div>'.format(diagnosis)
            else:
                html += '<div class="prof-diag prof-diag-ok"><strong>Status:</strong> No performance issues detected.</div>'

            html += '</div>'
            return mark_safe(html)

        profiling_breakdown.short_description = 'Profiling Breakdown'

        def headers_prettified(self, obj):
            return _prettify_json_field(obj.headers)

        headers_prettified.short_description = 'Headers'

        def body_prettified(self, obj):
            return _prettify_json_field(obj.body)

        body_prettified.short_description = 'Body'

        def response_prettified(self, obj):
            return _prettify_json_field(obj.response)

        response_prettified.short_description = 'Response'

        # Admin UI settings
        list_per_page = 20
        list_display = ('id', 'api', 'method', 'status_code', 'execution_time', 'added_on_time',)
        list_filter = ('added_on', 'status_code', 'method',)
        search_fields = ('body', 'response', 'headers', 'api',)
        readonly_fields = (
            'execution_time', 'client_ip_address', 'api',
            'headers_prettified', 'body_prettified', 'method', 'response_prettified',
            'status_code', 'added_on_time',
        )
        exclude = ('added_on', 'headers', 'body', 'response')

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
