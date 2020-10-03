from drf_api_logger.utils import database_log_enabled

LOGGER_THREAD = None

if database_log_enabled():
    from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
    import threading

    LOG_THREAD_NAME = 'insert_log_into_database'

    already_exists = False

    for t in threading.enumerate():
        if t.getName() == LOG_THREAD_NAME:
            already_exists = True

    if not already_exists:
        t = InsertLogIntoDatabase()
        t.daemon = True
        t.setName(LOG_THREAD_NAME)
        t.start()
        LOGGER_THREAD = t
