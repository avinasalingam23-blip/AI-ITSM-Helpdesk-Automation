import logging


class SafeAccessFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's full_path field includes query strings. Never log KB query text.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            values[2] = str(values[2]).split("?", 1)[0]
            record.args = tuple(values)
        return True


def configure_safe_access_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, SafeAccessFilter) for f in logger.filters):
        logger.addFilter(SafeAccessFilter())
