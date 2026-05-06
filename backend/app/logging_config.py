import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        level=logging.INFO,
        force=True,
    )
