from dataclasses import asdict, dataclass

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import OperationalError, ProgrammingError

from drf_api_logger import apps as logger_apps
from drf_api_logger.models import APILogsModel
from drf_api_logger.utils import database_log_enabled, is_api_logger_enabled


LEVEL_RANK = {"ok": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class DiagnosticResult:
    code: str
    level: str
    message: str
    hint: str = ""
    details: dict | None = None

    def as_dict(self):
        data = asdict(self)
        if self.details is None:
            data["details"] = {}
        return data


def run_diagnostics(database_alias=None):
    results = []
    results.extend(_check_logging_mode())
    results.extend(_check_queue_settings())
    results.extend(_check_payload_limits())
    results.extend(_check_masking_settings())
    results.extend(_check_profiling_settings())

    if database_log_enabled():
        database = database_alias or getattr(
            settings,
            "DRF_API_LOGGER_DEFAULT_DATABASE",
            "default",
        )
        results.extend(_check_database(database))
        results.extend(_check_worker())

    return results


def result_summary(results):
    highest = "ok"
    for result in results:
        if LEVEL_RANK[result.level] > LEVEL_RANK[highest]:
            highest = result.level
    return {
        "level": highest,
        "ok": len([result for result in results if result.level == "ok"]),
        "warning": len([result for result in results if result.level == "warning"]),
        "error": len([result for result in results if result.level == "error"]),
    }


def results_as_dict(results):
    return {
        "summary": result_summary(results),
        "results": [result.as_dict() for result in results],
    }


def should_fail(results, fail_level):
    if fail_level not in ("warning", "error"):
        return False
    threshold = LEVEL_RANK[fail_level]
    return any(LEVEL_RANK[result.level] >= threshold for result in results)


def _check_logging_mode():
    if not is_api_logger_enabled():
        return [
            DiagnosticResult(
                code="DRF001",
                level="warning",
                message="DRF API Logger is disabled.",
                hint=(
                    "Set DRF_API_LOGGER_DATABASE=True for database logging or "
                    "DRF_API_LOGGER_SIGNAL=True for signal-only logging."
                ),
            )
        ]

    if database_log_enabled():
        return [
            DiagnosticResult(
                code="DRF003",
                level="ok",
                message="Database logging is enabled.",
            )
        ]

    return [
        DiagnosticResult(
            code="DRF002",
            level="ok",
            message="Signal logging is enabled without database logging.",
            hint="Database table and worker checks are skipped in signal-only mode.",
        )
    ]


def _check_database(database):
    if not _database_alias_available(database):
        return [
            DiagnosticResult(
                code="DRF101",
                level="error",
                message='Configured log database alias "{}" is not available.'.format(database),
                hint="Check DATABASES and DRF_API_LOGGER_DEFAULT_DATABASE.",
                details={"database": database},
            )
        ]

    results = [
        DiagnosticResult(
            code="DRF102",
            level="ok",
            message='Configured log database alias "{}" is available.'.format(database),
            details={"database": database},
        )
    ]

    if _has_pending_migrations(database):
        results.append(
            DiagnosticResult(
                code="DRF103",
                level="error",
                message="DRF API Logger migrations are not fully applied.",
                hint="Run python manage.py migrate drf_api_logger before enabling production database logging.",
                details={"database": database},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF104",
                level="ok",
                message="DRF API Logger migrations are applied.",
                details={"database": database},
            )
        )

    if _database_table_exists(database):
        results.append(
            DiagnosticResult(
                code="DRF105",
                level="ok",
                message="API log table is available.",
                details={"database": database, "table": APILogsModel._meta.db_table},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF106",
                level="error",
                message="API log table is missing.",
                hint="Run migrations on the configured log database before enabling database logging.",
                details={"database": database, "table": APILogsModel._meta.db_table},
            )
        )

    return results


def _database_alias_available(database):
    return database in connections.databases


def _database_table_exists(database):
    try:
        connection = connections[database]
        return APILogsModel._meta.db_table in connection.introspection.table_names()
    except (KeyError, OperationalError, ProgrammingError):
        return False


def _has_pending_migrations(database):
    try:
        connection = connections[database]
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes("drf_api_logger")
        return bool(executor.migration_plan(targets))
    except (KeyError, OperationalError, ProgrammingError, ValueError):
        return True


def _check_worker():
    worker = logger_apps.LOGGER_THREAD
    if worker is None:
        return [
            DiagnosticResult(
                code="DRF202",
                level="warning",
                message="Background database worker is not available.",
                hint=(
                    "Confirm drf_api_logger is in INSTALLED_APPS, "
                    "DRF_API_LOGGER_DATABASE=True, and the app process has started."
                ),
            )
        ]

    status = worker.get_status() if hasattr(worker, "get_status") else {}
    is_alive = worker.is_alive() if hasattr(worker, "is_alive") else False
    if not is_alive:
        return [
            DiagnosticResult(
                code="DRF203",
                level="error",
                message="Background database worker is not running.",
                hint="Restart the application process and check startup logs.",
                details=status,
            )
        ]

    results = [
        DiagnosticResult(
            code="DRF201",
            level="ok",
            message="Background database worker is running.",
            details=status,
        )
    ]

    if status.get("failed_insert_count", 0) > 0:
        results.append(
            DiagnosticResult(
                code="DRF204",
                level="warning",
                message="Background worker has failed insert attempts.",
                hint="Check database connectivity, migrations, and log table availability.",
                details=status,
            )
        )

    if status.get("queue_backlog", 0) > status.get("batch_size", 50) * 5:
        results.append(
            DiagnosticResult(
                code="DRF205",
                level="warning",
                message="Background worker queue backlog is high.",
                hint="Check database write throughput, batch size, and request volume.",
                details=status,
            )
        )

    return results


def _check_queue_settings():
    results = []
    batch_size = getattr(settings, "DRF_LOGGER_QUEUE_MAX_SIZE", 50)
    interval = getattr(settings, "DRF_LOGGER_INTERVAL", 10)

    if not _is_positive_int(batch_size):
        results.append(
            DiagnosticResult(
                code="DRF401",
                level="error",
                message="DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0.",
                hint="Set DRF_LOGGER_QUEUE_MAX_SIZE to a positive integer such as 50 or 100.",
                details={"value": batch_size},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF402",
                level="ok",
                message="Queue batch size is valid.",
                details={"value": batch_size},
            )
        )

    if not _is_positive_int(interval):
        results.append(
            DiagnosticResult(
                code="DRF403",
                level="error",
                message="DRF_LOGGER_INTERVAL must be greater than 0.",
                hint="Set DRF_LOGGER_INTERVAL to a positive integer number of seconds.",
                details={"value": interval},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF404",
                level="ok",
                message="Queue flush interval is valid.",
                details={"value": interval},
            )
        )

    return results


def _check_payload_limits():
    results = []
    request_limit = getattr(settings, "DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE", 32768)
    response_limit = getattr(settings, "DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE", 65536)

    if request_limit == -1:
        results.append(
            DiagnosticResult(
                code="DRF301",
                level="warning",
                message="Request body logging is unbounded.",
                hint="Use a finite DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE in production.",
                details={"value": request_limit},
            )
        )
    elif not _is_int(request_limit):
        results.append(
            DiagnosticResult(
                code="DRF303",
                level="error",
                message="Request body size limit must be an integer.",
                hint="Set DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE to bytes or -1.",
                details={"type": type(request_limit).__name__},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF304",
                level="ok",
                message="Request body size limit is bounded.",
                details={"value": request_limit},
            )
        )

    if response_limit == -1:
        results.append(
            DiagnosticResult(
                code="DRF302",
                level="warning",
                message="Response body logging is unbounded.",
                hint="Use a finite DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE in production.",
                details={"value": response_limit},
            )
        )
    elif not _is_int(response_limit):
        results.append(
            DiagnosticResult(
                code="DRF305",
                level="error",
                message="Response body size limit must be an integer.",
                hint="Set DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE to bytes or -1.",
                details={"type": type(response_limit).__name__},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                code="DRF306",
                level="ok",
                message="Response body size limit is bounded.",
                details={"value": response_limit},
            )
        )

    return results


def _check_masking_settings():
    configured = getattr(settings, "DRF_API_LOGGER_EXCLUDE_KEYS", [])
    if configured and not isinstance(configured, (list, tuple)):
        return [
            DiagnosticResult(
                code="DRF501",
                level="error",
                message="DRF_API_LOGGER_EXCLUDE_KEYS must be a list or tuple.",
                hint="Use a list such as ['password', 'token', 'api_key'].",
                details={"type": type(configured).__name__},
            )
        ]

    if not configured:
        return [
            DiagnosticResult(
                code="DRF502",
                level="warning",
                message="No application-specific masking keys are configured.",
                hint="Add domain-specific secrets to DRF_API_LOGGER_EXCLUDE_KEYS before production use.",
            )
        ]

    return [
        DiagnosticResult(
            code="DRF503",
            level="ok",
            message="Application-specific masking keys are configured.",
            details={"count": len(configured)},
        )
    ]


def _check_profiling_settings():
    if not getattr(settings, "DRF_API_LOGGER_ENABLE_PROFILING", False):
        return [
            DiagnosticResult(
                code="DRF601",
                level="ok",
                message="Profiling is disabled.",
            )
        ]

    sample_rate = getattr(settings, "DRF_API_LOGGER_PROFILING_SAMPLE_RATE", 1.0)
    if not isinstance(sample_rate, (int, float)) or isinstance(sample_rate, bool):
        return [
            DiagnosticResult(
                code="DRF602",
                level="error",
                message="Profiling sample rate must be numeric.",
                hint="Set DRF_API_LOGGER_PROFILING_SAMPLE_RATE between 0.0 and 1.0.",
                details={"type": type(sample_rate).__name__},
            )
        ]

    if float(sample_rate) >= 1.0:
        return [
            DiagnosticResult(
                code="DRF603",
                level="warning",
                message="Profiling is enabled for every logged request.",
                hint="Use a lower sample rate such as 0.1 on high-traffic production systems.",
                details={"value": sample_rate},
            )
        ]

    return [
        DiagnosticResult(
            code="DRF604",
            level="ok",
            message="Profiling sample rate is limited.",
            details={"value": sample_rate},
        )
    ]


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value):
    return _is_int(value) and value > 0
