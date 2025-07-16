import logging
from copy import deepcopy
from pathlib import Path

from dareplane_utils.logging.logger import get_logger

logger = get_logger("stroop_task", add_console_handler=True)


def add_file_handler(file_path: Path = Path("stroop_task.log")):
    # add a local file handler
    fh = logging.FileHandler(file_path)
    formatter = deepcopy(logger.handlers[0].formatter)
    formatter.no_color = True  # type: ignore

    fh.formatter = formatter

    logger.addHandler(fh)
