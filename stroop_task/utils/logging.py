import logging

from dareplane_utils.logging.logger import get_logger

logger = get_logger("stroop_task", add_console_handler=True)

# add a local file handler
fh = logging.FileHandler("stroop_task.log")
fh.formatter = logger.handlers[1].formatter
logger.addHandler(fh)
