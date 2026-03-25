import logging
from logging.config import dictConfig
import os
from huggingface_hub import utils


def setup_logging():
    utils.disable_progress_bars()
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,

        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },

        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },

        "loggers": {
            "httpx": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            },

            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            },

            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },

            "urllib3": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            },
        }
    })