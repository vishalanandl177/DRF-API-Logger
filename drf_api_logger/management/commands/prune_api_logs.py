from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from drf_api_logger.utils import database_log_enabled


class Command(BaseCommand):
    help = 'Delete old DRF API Logger database rows in safe batches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            help='Delete logs older than this many days.',
        )
        parser.add_argument(
            '--before',
            help='Delete logs added before this date in YYYY-MM-DD format.',
        )
        parser.add_argument(
            '--database',
            help='Database alias to prune. Defaults to DRF_API_LOGGER_DEFAULT_DATABASE or default.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of rows to delete per batch. Default: 1000.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report how many rows would be deleted without deleting them.',
        )

    def handle(self, *args, **options):
        if not database_log_enabled():
            raise CommandError('DRF_API_LOGGER_DATABASE must be True to prune database logs.')

        batch_size = options['batch_size']
        if batch_size < 1:
            raise CommandError('--batch-size must be greater than 0.')

        cutoff = self._get_cutoff(options.get('days'), options.get('before'))
        database = options.get('database') or getattr(
            settings,
            'DRF_API_LOGGER_DEFAULT_DATABASE',
            'default',
        )

        from drf_api_logger.models import APILogsModel

        queryset = APILogsModel.objects.using(database).filter(added_on__lt=cutoff)
        matching_count = queryset.count()

        if options['dry_run']:
            self.stdout.write(
                'Would delete {} API log row(s) older than {} from database "{}".'.format(
                    matching_count,
                    self._format_cutoff(cutoff),
                    database,
                )
            )
            return

        deleted_count = self._delete_in_batches(APILogsModel, database, cutoff, batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                'Deleted {} API log row(s) older than {} from database "{}".'.format(
                    deleted_count,
                    self._format_cutoff(cutoff),
                    database,
                )
            )
        )

    def _get_cutoff(self, days, before):
        if (days is None and before is None) or (days is not None and before is not None):
            raise CommandError('Provide exactly one of --days or --before.')

        if days is not None:
            if days < 1:
                raise CommandError('--days must be greater than 0.')
            return self._now() - timedelta(days=days)

        try:
            parsed_date = datetime.strptime(before, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('--before must use YYYY-MM-DD format.')

        cutoff = datetime.combine(parsed_date, time.min)
        if settings.USE_TZ:
            return timezone.make_aware(cutoff, timezone.get_current_timezone())
        return cutoff

    def _now(self):
        if settings.USE_TZ:
            return timezone.now()
        return datetime.now()

    def _delete_in_batches(self, model, database, cutoff, batch_size):
        deleted_count = 0
        while True:
            ids = list(
                model.objects.using(database)
                .filter(added_on__lt=cutoff)
                .order_by('added_on', 'pk')
                .values_list('pk', flat=True)[:batch_size]
            )
            if not ids:
                break

            batch_deleted, _ = model.objects.using(database).filter(pk__in=ids).delete()
            deleted_count += batch_deleted

        return deleted_count

    def _format_cutoff(self, cutoff):
        return cutoff.isoformat()
