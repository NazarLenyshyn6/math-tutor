import logging

LOGGING_FORMAT = "[%(asctime)s | %(name)s | %(levelname)s]: %(message)s"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a logger with the specified name and logging level,
    configured to avoid unnecessary logs from other libraries.

    Args:
        name (str): Name of the logger.
        level (int, optional): Logging level (e.g., logging.DEBUG, logging.INFO). Defaults to logging.INFO.

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter(LOGGING_FORMAT)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger
