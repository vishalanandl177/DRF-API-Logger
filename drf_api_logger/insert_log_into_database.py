from queue import Queue
import time
from django.conf import settings
from threading import Thread
from django.db.utils import OperationalError

from drf_api_logger.models import APILogsModel


class InsertLogIntoDatabase(Thread):

    def __init__(self):
        super().__init__()

        self.DRF_API_LOGGER_DEFAULT_DATABASE = 'default'
        if hasattr(settings, 'DRF_API_LOGGER_DEFAULT_DATABASE'):
            self.DRF_API_LOGGER_DEFAULT_DATABASE = settings.DRF_API_LOGGER_DEFAULT_DATABASE

        self.DRF_LOGGER_QUEUE_MAX_SIZE = 50  # Default queue size 50
        if hasattr(settings, 'DRF_LOGGER_QUEUE_MAX_SIZE'):
            self.DRF_LOGGER_QUEUE_MAX_SIZE = settings.DRF_LOGGER_QUEUE_MAX_SIZE

        if self.DRF_LOGGER_QUEUE_MAX_SIZE < 1:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Value of DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0
            """)

        self.DRF_LOGGER_INTERVAL = 10  # Default DB insertion interval is 10 seconds.
        if hasattr(settings, 'DRF_LOGGER_INTERVAL'):
            self.DRF_LOGGER_INTERVAL = settings.DRF_LOGGER_INTERVAL

            if self.DRF_LOGGER_INTERVAL < 1:
                raise Exception("""
                DRF API LOGGER EXCEPTION
                Value of DRF_LOGGER_INTERVAL must be greater than 0
                """)

        self._queue = Queue(maxsize=self.DRF_LOGGER_QUEUE_MAX_SIZE)

    def run(self) -> None:
        self.start_queue_process()

    def put_log_data(self, data):
        self._queue.put(APILogsModel(**data))

        if self._queue.qsize() >= self.DRF_LOGGER_QUEUE_MAX_SIZE:
            self._start_bulk_insertion()

    def start_queue_process(self):
        while True:
            time.sleep(self.DRF_LOGGER_INTERVAL)
            self._start_bulk_insertion()

    def _start_bulk_insertion(self):
        bulk_item = []
        while not self._queue.empty():
            bulk_item.append(self._queue.get())
        if bulk_item:
            self._insert_into_data_base(bulk_item)

    def _insert_into_data_base(self, bulk_item):
        try:
            APILogsModel.objects.using(self.DRF_API_LOGGER_DEFAULT_DATABASE).bulk_create(bulk_item)
        except OperationalError:
            raise Exception("""
            DRF API LOGGER EXCEPTION
            Model does not exists.
            Did you forget to migrate?
            """)
        except Exception as e:
            print('DRF API LOGGER EXCEPTION:', e)
