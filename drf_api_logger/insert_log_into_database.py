import atexit
import signal
from queue import Empty, Queue
from importlib import import_module
from django.conf import settings
from threading import Thread, Event, Lock
from django.db.utils import OperationalError
from drf_api_logger.models import APILogsModel


class InsertLogIntoDatabase(Thread):
    """
    A background thread that handles asynchronous, batched insertion of API log data
    into the database using Django models. The insertion behavior (such as queue size
    and interval) can be customized via Django settings.
    """

    def __init__(self):
        super().__init__()

        # Event used to gracefully stop the thread
        self._stop_event = Event()
        self._flush_event = Event()
        self._stats_lock = Lock()
        self._dropped_count = 0
        self._inserted_count = 0
        self._failed_insert_count = 0
        self._atexit_registered = False

        # Determine the default database to use for log insertion
        self.DRF_API_LOGGER_DEFAULT_DATABASE = 'default'
        if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
            self.DRF_API_LOGGER_DEFAULT_DATABASE = settings.DRF_API_LOGGER_DEFAULT_DATABASE

        # Set the batch size threshold; default is 50
        self.DRF_LOGGER_QUEUE_MAX_SIZE = 50
        if hasattr(settings, 'DRF_LOGGER_QUEUE_MAX_SIZE'):
            self.DRF_LOGGER_QUEUE_MAX_SIZE = settings.DRF_LOGGER_QUEUE_MAX_SIZE

        if self.DRF_LOGGER_QUEUE_MAX_SIZE < 1:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Value of DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0
            """)

        # Set the interval (in seconds) to wait before inserting queued logs into DB
        self.DRF_LOGGER_INTERVAL = 10
        if hasattr(settings, 'DRF_LOGGER_INTERVAL'):
            self.DRF_LOGGER_INTERVAL = settings.DRF_LOGGER_INTERVAL

            if self.DRF_LOGGER_INTERVAL < 1:
                raise Exception("""
                DRF API LOGGER EXCEPTION
                Value of DRF_LOGGER_INTERVAL must be greater than 0
                """)

        self.custom_handler = getattr(settings, 'DRF_API_LOGGER_CUSTOM_HANDLER', None)
        if self.custom_handler:
            self.custom_handler = self._import_custom_handler(self.custom_handler)

        # Keep this unbounded so request threads enqueue quickly. The setting
        # controls bulk insert batch size, not a request-path blocking limit.
        self._queue = Queue()

        # Register signal handlers for clean exit on termination signals
        try:
            signal.signal(signal.SIGINT, self._clean_exit)
            signal.signal(signal.SIGTERM, self._clean_exit)
        except ValueError:
            pass

    def run(self) -> None:
        """
        Entry point for the thread. Starts the queue processing loop.
        """
        if not self._atexit_registered:
            atexit.register(self.shutdown)
            self._atexit_registered = True
        self.start_queue_process()

    def put_log_data(self, data):
        """
        Adds a new log entry to the queue.
        If the queue reaches the batch threshold, wakes the background worker.

        Args:
            data (dict): Dictionary containing fields for APILogsModel.
        """
        if self.custom_handler:
            data = self.custom_handler(data)
            if data is None:
                self._increment_stat('_dropped_count')
                return

        try:
            self._queue.put_nowait(APILogsModel(**data))
        except Exception as e:
            self._increment_stat('_dropped_count')
            print('DRF API LOGGER EXCEPTION:', e)
            return

        # If queue reaches the batch threshold, wake the worker to flush.
        if self._queue.qsize() >= self.DRF_LOGGER_QUEUE_MAX_SIZE:
            self._flush_event.set()

    def start_queue_process(self):
        """
        Runs in a loop (until stopped) and periodically inserts all queued logs
        into the database in bulk, based on the defined interval.
        """
        while not self._stop_event.is_set():
            self._flush_event.wait(self.DRF_LOGGER_INTERVAL)
            self._flush_event.clear()
            self._start_bulk_insertion()

    def _start_bulk_insertion(self):
        """
        Pulls all available items from the queue and inserts them into the database
        using Django's bulk_create method for performance.
        """
        while True:
            bulk_item = []
            while len(bulk_item) < self.DRF_LOGGER_QUEUE_MAX_SIZE:
                try:
                    bulk_item.append(self._queue.get_nowait())
                except Empty:
                    break

            if not bulk_item:
                break
            self._insert_into_data_base(bulk_item)

    def _insert_into_data_base(self, bulk_item):
        """
        Performs the actual insertion of log items into the database.

        Args:
            bulk_item (list): A list of APILogsModel instances to insert.

        Raises:
            Exception: If the model doesn't exist or another database error occurs.
        """
        try:
            APILogsModel.objects.using(self.DRF_API_LOGGER_DEFAULT_DATABASE).bulk_create(bulk_item)
            self._increment_stat('_inserted_count', len(bulk_item))
        except OperationalError:
            self._increment_stat('_failed_insert_count', len(bulk_item))
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Model does not exist.
            Did you forget to migrate?
            """)
        except Exception as e:
            self._increment_stat('_failed_insert_count', len(bulk_item))
            # Logs other unexpected exceptions to the console
            print('DRF API LOGGER EXCEPTION:', e)

    def _import_custom_handler(self, handler_path):
        """
        Import the custom handler function from a given string path.
        """
        module_path, func_name = handler_path.rsplit('.', 1)
        module = import_module(module_path)
        return getattr(module, func_name)

    def _clean_exit(self, signum, frame):
        """
        Signal handler that is called when the process is being terminated (e.g., via SIGINT or SIGTERM).
        It sets the stop event and flushes any remaining logs in the queue to the database.

        Args:
            signum: Signal number received.
            frame: Current stack frame (ignored here).
        """
        self.shutdown()
        raise SystemExit(0)

    def shutdown(self):
        """
        Stop the worker loop and flush any queued logs.
        """
        self._stop_event.set()
        self._flush_event.set()
        self._start_bulk_insertion()

    def get_status(self):
        """
        Return queue and insertion stats for health checks or diagnostics.
        """
        with self._stats_lock:
            return {
                'queue_backlog': self._queue.qsize(),
                'batch_size': self.DRF_LOGGER_QUEUE_MAX_SIZE,
                'interval': self.DRF_LOGGER_INTERVAL,
                'dropped_count': self._dropped_count,
                'inserted_count': self._inserted_count,
                'failed_insert_count': self._failed_insert_count,
            }

    def _increment_stat(self, name, amount=1):
        with self._stats_lock:
            setattr(self, name, getattr(self, name) + amount)
