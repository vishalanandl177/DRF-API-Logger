"""
Test cases for DRF API Logger management commands.
"""
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from drf_api_logger.models import APILogsModel


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestPruneAPILogsCommand(TestCase):
    """Test cases for pruning old API logs."""

    def create_log(self, api, added_on):
        return APILogsModel.objects.create(
            api=api,
            headers='{}',
            body='',
            method='GET',
            client_ip_address='127.0.0.1',
            response='{}',
            status_code=200,
            execution_time=0.1,
            added_on=added_on,
        )

    def test_requires_days_or_before_cutoff(self):
        """The command should not delete anything without an explicit cutoff."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs')

        self.assertIn('Provide exactly one of --days or --before', str(context.exception))

    def test_dry_run_reports_matching_rows_without_deleting(self):
        """Dry runs should count matching rows but leave the table unchanged."""
        now = timezone.now()
        self.create_log('/api/old/', now - timedelta(days=40))
        self.create_log('/api/recent/', now - timedelta(days=5))
        output = StringIO()

        call_command('prune_api_logs', '--days', '30', '--dry-run', stdout=output)

        self.assertEqual(APILogsModel.objects.count(), 2)
        self.assertIn('Would delete 1 API log row(s)', output.getvalue())

    def test_days_cutoff_deletes_only_older_logs(self):
        """A days cutoff should delete rows older than the calculated cutoff."""
        now = timezone.now()
        old_log = self.create_log('/api/old/', now - timedelta(days=40))
        recent_log = self.create_log('/api/recent/', now - timedelta(days=5))
        output = StringIO()

        call_command('prune_api_logs', '--days', '30', stdout=output)

        remaining_ids = set(APILogsModel.objects.values_list('id', flat=True))
        self.assertNotIn(old_log.id, remaining_ids)
        self.assertIn(recent_log.id, remaining_ids)
        self.assertIn('Deleted 1 API log row(s)', output.getvalue())

    def test_before_date_deletes_logs_before_that_date(self):
        """A before-date cutoff should delete logs strictly before that date."""
        older = self.create_log('/api/may/', datetime(2026, 5, 31, tzinfo=datetime_timezone.utc))
        same_day = self.create_log('/api/june/', datetime(2026, 6, 1, tzinfo=datetime_timezone.utc))

        call_command('prune_api_logs', '--before', '2026-06-01', stdout=StringIO())

        remaining_ids = set(APILogsModel.objects.values_list('id', flat=True))
        self.assertNotIn(older.id, remaining_ids)
        self.assertIn(same_day.id, remaining_ids)

    def test_batch_size_deletes_all_matching_rows(self):
        """Small batches should still delete every row matching the cutoff."""
        now = timezone.now()
        for index in range(5):
            self.create_log('/api/old/{}/'.format(index), now - timedelta(days=60, minutes=index))
        self.create_log('/api/recent/', now - timedelta(days=1))

        call_command('prune_api_logs', '--days', '30', '--batch-size', '2', stdout=StringIO())

        self.assertEqual(APILogsModel.objects.count(), 1)
        self.assertEqual(APILogsModel.objects.get().api, '/api/recent/')

    def test_rejects_invalid_batch_size(self):
        """Batch size must be positive to avoid a non-progressing delete loop."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs', '--days', '30', '--batch-size', '0')

        self.assertIn('--batch-size must be greater than 0', str(context.exception))

    def test_rejects_days_and_before_together(self):
        """The command should require one unambiguous cutoff mode."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs', '--days', '30', '--before', '2026-06-01')

        self.assertIn('Provide exactly one of --days or --before', str(context.exception))

    def test_rejects_invalid_days(self):
        """The days cutoff must be positive."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs', '--days', '0')

        self.assertIn('--days must be greater than 0', str(context.exception))

    def test_rejects_invalid_before_format(self):
        """The before cutoff should only accept YYYY-MM-DD input."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs', '--before', '06/01/2026')

        self.assertIn('--before must use YYYY-MM-DD format', str(context.exception))

    @override_settings(DRF_API_LOGGER_DATABASE=False)
    def test_requires_database_logging_enabled(self):
        """The command should not import or prune database logs when DB logging is disabled."""
        with self.assertRaises(CommandError) as context:
            call_command('prune_api_logs', '--days', '30')

        self.assertIn('DRF_API_LOGGER_DATABASE must be True', str(context.exception))


class TestDRFAPILoggerDoctorCommand(TestCase):
    """Test cases for production diagnostics command output and exit behavior."""

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_text_output_includes_summary_results_and_hints(self):
        output = StringIO()

        call_command('drf_api_logger_doctor', stdout=output)

        content = output.getvalue()
        self.assertIn('DRF API Logger diagnostics', content)
        self.assertIn('Summary:', content)
        self.assertIn('WARNING DRF001 DRF API Logger is disabled.', content)
        self.assertIn('hint:', content)

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_json_output_is_machine_readable(self):
        import json

        output = StringIO()

        call_command('drf_api_logger_doctor', '--format', 'json', stdout=output)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload['summary']['warning'], 1)
        self.assertEqual(payload['results'][0]['code'], 'DRF001')
        self.assertEqual(payload['results'][0]['details'], {})

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_fail_level_warning_raises_command_error(self):
        output = StringIO()

        with self.assertRaises(CommandError) as context:
            call_command('drf_api_logger_doctor', '--fail-level', 'warning', stdout=output)

        self.assertIn('DRF API Logger diagnostics failed at warning level', str(context.exception))

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    def test_fail_level_error_raises_for_error_result(self):
        output = StringIO()

        with self.assertRaises(CommandError) as context:
            call_command('drf_api_logger_doctor', '--database', 'missing', stdout=output)

        self.assertIn('DRF API Logger diagnostics failed at error level', str(context.exception))
