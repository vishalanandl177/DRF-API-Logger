from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from drf_api_logger.utils import database_log_enabled


@override_settings(DRF_API_LOGGER_DATABASE=True)
class AdminChartDataEndpointTests(TestCase):
    def setUp(self):
        if not database_log_enabled():
            self.skipTest("Database logging is not enabled")

        from drf_api_logger.models import APILogsModel

        self.APILogsModel = APILogsModel
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="password",
        )
        self.client.force_login(self.user)
        now = timezone.now()
        self.APILogsModel.objects.create(
            api="/api/one/",
            headers="{}",
            body="",
            method="GET",
            client_ip_address="127.0.0.1",
            response="{}",
            status_code=200,
            execution_time=0.1,
            added_on=now - timedelta(days=1),
            sql_query_count=3,
        )
        self.APILogsModel.objects.create(
            api="/api/two/",
            headers="{}",
            body="",
            method="POST",
            client_ip_address="127.0.0.1",
            response="{}",
            status_code=500,
            execution_time=0.2,
            added_on=now,
            sql_query_count=11,
        )
        self.APILogsModel.objects.create(
            api="/api/three/",
            headers="{}",
            body="",
            method="GET",
            client_ip_address="127.0.0.1",
            response="{}",
            status_code=500,
            execution_time=0.3,
            added_on=now,
            sql_query_count=None,
        )

    def test_changelist_does_not_precompute_chart_data(self):
        response = self.client.get(
            reverse("admin:drf_api_logger_apilogsmodel_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("analytics", response.context_data)
        self.assertNotIn("status_code_count_keys", response.context_data)
        self.assertNotIn("status_code_count_values", response.context_data)
        self.assertNotIn("sql_distribution", response.context_data)

    def test_api_calls_by_day_chart_data_uses_current_admin_filters(self):
        response = self.client.get(
            reverse(
                "admin:drf_api_logger_apilogsmodel_chart_data",
                args=["api-calls-by-day"],
            ),
            {"method__exact": "GET"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["chart"], "api-calls-by-day")
        self.assertEqual(data["label"], "Number of API calls")
        self.assertEqual(sum(item["y"] for item in data["data"]), 2)

    def test_api_calls_by_status_code_chart_data_uses_current_admin_filters(self):
        response = self.client.get(
            reverse(
                "admin:drf_api_logger_apilogsmodel_chart_data",
                args=["api-calls-by-status-code"],
            ),
            {"method__exact": "GET"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["chart"], "api-calls-by-status-code")
        self.assertEqual(data["labels"], [200, 500])
        self.assertEqual(data["values"], [1, 1])

    @override_settings(DRF_API_LOGGER_ENABLE_PROFILING=True)
    def test_sql_queries_by_day_chart_data_requires_profiling_and_filters(self):
        response = self.client.get(
            reverse(
                "admin:drf_api_logger_apilogsmodel_chart_data",
                args=["sql-queries-by-day"],
            ),
            {"method__exact": "POST"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["chart"], "sql-queries-by-day")
        self.assertEqual(data["label"], "Avg SQL queries per request")
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["y"], 11.0)

    def test_unknown_chart_data_returns_404(self):
        response = self.client.get(
            reverse(
                "admin:drf_api_logger_apilogsmodel_chart_data",
                args=["private-fields"],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_chart_data_requires_admin_authentication(self):
        self.client.logout()

        response = self.client.get(
            reverse(
                "admin:drf_api_logger_apilogsmodel_chart_data",
                args=["api-calls-by-day"],
            )
        )

        self.assertEqual(response.status_code, 302)
