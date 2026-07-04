from contextvars import ContextVar


_correlation_context = ContextVar('drf_api_logger_correlation_context', default={})


def set_correlation_context(context):
    if type(context) is not dict:
        context = {}
    _correlation_context.set(context.copy())


def get_correlation_context():
    return _correlation_context.get({}).copy()


def clear_correlation_context():
    _correlation_context.set({})
