import signal
from queue import Queue
import time
from importlib import import_module
from django.conf import settings
from threading import Thread, Event
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

        # Determine the default database to use for log insertion
        self.DRF_API_LOGGER_DEFAULT_DATABASE = 'default'
        if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
            self.DRF_API_LOGGER_DEFAULT_DATABASE = settings.DRF_API_LOGGER_DEFAULT_DATABASE

        # Set the max size of the queue; default is 50
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

        # Thread-safe FIFO queue for storing log data before bulk insertion
        self._queue = Queue(maxsize=self.DRF_LOGGER_QUEUE_MAX_SIZE)

        # Register signal handlers for clean exit on termination signals
        signal.signal(signal.SIGINT, self._clean_exit)
        signal.signal(signal.SIGTERM, self._clean_exit)

    def run(self) -> None:
        """
        Entry point for the thread. Starts the queue processing loop.
        """
        self.start_queue_process()

    def put_log_data(self, data):
        """
        Adds a new log entry to the queue.
        If the queue reaches its maximum size, triggers a bulk insert immediately.

        Args:
            data (dict): Dictionary containing fields for APILogsModel.
        """
        self._queue.put(APILogsModel(**data))

        # If queue is full, trigger immediate flush to the DB
        if self._queue.qsize() >= self.DRF_LOGGER_QUEUE_MAX_SIZE:
            self._start_bulk_insertion()

    def start_queue_process(self):
        """
        Runs in a loop (until stopped) and periodically inserts all queued logs
        into the database in bulk, based on the defined interval.
        """
        while not self._stop_event.is_set():
            time.sleep(self.DRF_LOGGER_INTERVAL)
            self._start_bulk_insertion()

    def _start_bulk_insertion(self):
        """
        Pulls all available items from the queue and inserts them into the database
        using Django's bulk_create method for performance.
        """
        bulk_item = []
        while not self._queue.empty():
            bulk_item.append(self._queue.get())

        if bulk_item:
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
        except OperationalError:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Model does not exist.
            Did you forget to migrate?
            """)
        except Exception as e:
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
        self._stop_event.set()
        self._start_bulk_insertion()
