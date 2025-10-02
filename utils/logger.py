import logging 
import sys

def setup_logger(name: str = "avito_parser", level = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger