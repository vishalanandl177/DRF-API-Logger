import json

from django.core.management.base import BaseCommand, CommandError

from drf_api_logger.diagnostics import (
    results_as_dict,
    run_diagnostics,
    should_fail,
)


class Command(BaseCommand):
    help = 'Validate DRF API Logger production readiness.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            help='Database alias to inspect. Defaults to DRF_API_LOGGER_DEFAULT_DATABASE or default.',
        )
        parser.add_argument(
            '--format',
            choices=('text', 'json'),
            default='text',
            help='Output format. Default: text.',
        )
        parser.add_argument(
            '--fail-level',
            choices=('warning', 'error'),
            default='error',
            help='Raise CommandError when diagnostics include this level or worse. Default: error.',
        )

    def handle(self, *args, **options):
        results = run_diagnostics(database_alias=options.get('database'))
        payload = results_as_dict(results)

        if options['format'] == 'json':
            self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        else:
            self._write_text(payload)

        if should_fail(results, options['fail_level']):
            raise CommandError(
                'DRF API Logger diagnostics failed at {} level.'.format(
                    options['fail_level']
                )
            )

    def _write_text(self, payload):
        summary = payload['summary']
        self.stdout.write('DRF API Logger diagnostics')
        self.stdout.write(
            'Summary: {ok} ok, {warning} warning, {error} error'.format(**summary)
        )
        for result in payload['results']:
            self.stdout.write(
                '{level} {code} {message}'.format(
                    level=result['level'].upper(),
                    code=result['code'],
                    message=result['message'],
                )
            )
            if result.get('hint'):
                self.stdout.write('  hint: {}'.format(result['hint']))
