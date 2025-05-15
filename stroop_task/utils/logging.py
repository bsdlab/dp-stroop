import logging
from pathlib import Path

from dareplane_utils.logging.logger import get_logger

logger = get_logger("stroop_task", add_console_handler=True)


def add_file_handler(file_path: Path = "stroop_task.log"):
    # add a local file handler
    fh = logging.FileHandler(file_path)
    fh.formatter = logger.handlers[0].formatter

    logger.addHandler(fh)
