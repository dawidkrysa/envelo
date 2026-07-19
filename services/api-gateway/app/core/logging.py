import logging.config

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    logging.config.dictConfig(
        {
            "version": 1,
            # Leave uvicorn loggers
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level,
            },
        }
    )
