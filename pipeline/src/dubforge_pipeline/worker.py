import logging

from dubforge_pipeline.logging_config import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    configure_logging()
    logger.info("DubForge worker is ready; job handlers will be added with the shared contract.")


if __name__ == "__main__":
    run()
