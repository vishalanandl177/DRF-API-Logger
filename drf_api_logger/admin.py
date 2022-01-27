from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.db.models import Count
from drf_api_logger.utils import database_log_enabled

if database_log_enabled():
    from drf_api_logger.models import APILogsModel
    from django.utils.translation import gettext_lazy as _

    class SlowAPIsFilter(admin.SimpleListFilter):
        title = _('API Performance')

        # Parameter for the filter that will be used in the URL query.
        parameter_name = 'api_performance'

        def __init__(self, request, params, model, model_admin):
            super().__init__(request, params, model, model_admin)
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                if type(settings.DRF_API_LOGGER_SLOW_API_ABOVE) == int:  # Making sure for integer value.
                    self._DRF_API_LOGGER_SLOW_API_ABOVE = settings.DRF_API_LOGGER_SLOW_API_ABOVE / 1000  # Converting to seconds.

        def lookups(self, request, model_admin):
            """
            Returns a list of tuples. The first element in each
            tuple is the coded value for the option that will
            appear in the URL query. The second element is the
            human-readable name for the option that will appear
            in the right sidebar.
            """
            slow = 'Slow'
            fast = 'Fast'
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                slow += ', >={}ms'.format(settings.DRF_API_LOGGER_SLOW_API_ABOVE)
                fast += ', <{}ms'.format(settings.DRF_API_LOGGER_SLOW_API_ABOVE)

            return (
                ('slow', _(slow)),
                ('fast', _(fast)),
            )

        def queryset(self, request, queryset):
            """
            Returns the filtered queryset based on the value
            provided in the query string and retrievable via
            `self.value()`.
            """
            # to decide how to filter the queryset.
            if self.value() == 'slow':
                return queryset.filter(execution_time__gte=self._DRF_API_LOGGER_SLOW_API_ABOVE)
            if self.value() == 'fast':
                return queryset.filter(execution_time__lt=self._DRF_API_LOGGER_SLOW_API_ABOVE)

            return queryset

    class APILogsAdmin(admin.ModelAdmin):

        def __init__(self, model, admin_site):
            super().__init__(model, admin_site)
            self._DRF_API_LOGGER_TIMEDELTA = 0
            if hasattr(settings, 'DRF_API_LOGGER_SLOW_API_ABOVE'):
                if type(settings.DRF_API_LOGGER_SLOW_API_ABOVE) == int:  # Making sure for integer value.
                    self.list_filter += (SlowAPIsFilter,)
            if hasattr(settings, 'DRF_API_LOGGER_TIMEDELTA'):
                if type(settings.DRF_API_LOGGER_TIMEDELTA) == int:  # Making sure for integer value.
                    self._DRF_API_LOGGER_TIMEDELTA = settings.DRF_API_LOGGER_TIMEDELTA

        def added_on_time(self, obj):
            return (obj.added_on + timedelta(minutes=self._DRF_API_LOGGER_TIMEDELTA)).strftime("%d %b %Y %H:%M:%S")

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
            try:
                filtered_query_set = response.context_data["cl"].queryset
            except:
                return response
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

        def get_queryset(self, request):
            return super(APILogsAdmin, self).get_queryset(request)

        def has_add_permission(self, request, obj=None):
            return False

        def has_change_permission(self, request, obj=None):
            return False


    admin.site.register(APILogsModel, APILogsAdmin)
