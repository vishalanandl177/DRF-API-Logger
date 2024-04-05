from queue import Queue
import time
from threading import Thread
from django.conf import settings
from django.db.utils import OperationalError

from drf_api_logger.models import APILogs


class InsertLogIntoDatabase(Thread):

    def __init__(self):
        super().__init__()

        self.default_database = 'default'
        if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
            self.default_database = settings.DRF_API_LOGGER_DEFAULT_DATABASE

        self.queue_max_size = 50  # Default queue size 50
        if hasattr(settings, 'DRF_LOGGER_QUEUE_MAX_SIZE'):
            self.queue_max_size = settings.DRF_LOGGER_QUEUE_MAX_SIZE

        if self.queue_max_size < 1:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Value of DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0
            """)

        self.interval = 10  # Default DB insertion interval is 10 seconds.
        if hasattr(settings, 'DRF_LOGGER_INTERVAL'):
            self.interval = settings.DRF_LOGGER_INTERVAL

            if self.interval < 1:
                raise Exception("""
                DRF API LOGGER EXCEPTION
                Value of DRF_LOGGER_INTERVAL must be greater than 0
                """)

        self._queue = Queue(maxsize=self.queue_max_size)

    def run(self) -> None:
        self.start_queue_process()

    def put_log_data(self, data):
        self._queue.put(APILogs(**data))

        if self._queue.qsize() >= self.queue_max_size:
            self._start_bulk_insertion()

    def start_queue_process(self):
        while True:
            time.sleep(self.interval)
            self._start_bulk_insertion()

    def _start_bulk_insertion(self):
        bulk_item = []
        while not self._queue.empty():
            bulk_item.append(self._queue.get())
        if bulk_item:
            self._insert_into_data_base(bulk_item)

    def _insert_into_data_base(self, bulk_item):
        try:
            APILogs.objects.using(self.default_database).bulk_create(bulk_item)
        except OperationalError:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Model does not exists.
            Did you forget to migrate?
            """)
        except Exception as e:
            print('DRF API LOGGER EXCEPTION:', e)
