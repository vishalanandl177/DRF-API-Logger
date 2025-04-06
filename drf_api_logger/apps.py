import os

from django.apps import AppConfig

from drf_api_logger.utils import database_log_enabled

# Global variable to hold the reference to the logger thread
LOGGER_THREAD = None


class LoggerConfig(AppConfig):
    """
    Django AppConfig for the DRF API Logger app.
    This is the configuration class for the Django app named 'drf_api_logger'.
    It is used to initialize application-level settings and perform startup tasks.
    """
    name = 'drf_api_logger'
    verbose_name = 'DRF API Logger'

    def ready(self):
        """
        Called when the app is ready.
        Starts the background thread that inserts API logs into the database,
        but only in the main process (to avoid duplication on autoreload).
        """
        global LOGGER_THREAD

        # Prevent running this logic in the autoreloader subprocess (used during development)
        if os.environ.get('RUN_MAIN') == 'true':
            # Check if database logging is enabled via settings
            if database_log_enabled():
                from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
                import threading

                LOG_THREAD_NAME = 'insert_log_into_database'

                # Check if the thread is already running to avoid starting multiple threads
                already_exists = False
                for t in threading.enumerate():
                    if t.name == LOG_THREAD_NAME:
                        already_exists = True
                        break

                # If the thread is not already running, create and start it
                if not already_exists:
                    t = InsertLogIntoDatabase()  # This is a subclass of threading.Thread
                    t.daemon = True              # Make it a daemon so it shuts down with the main thread
                    t.name = LOG_THREAD_NAME     # Assign a name to the thread for easy identification
                    t.start()                    # Start the background log insertion thread
                    LOGGER_THREAD = t
