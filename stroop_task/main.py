# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from subprocess import Popen
from typing import Optional

import pyglet
import yaml
from fire import Fire

from stroop_task.context import load_context
from stroop_task.task_manager import (
    StroopClassicTaskStateManager,
    StroopTaskStateManager,
    on_draw,
    on_escape_exit_handler,
)
from stroop_task.utils.logging import add_file_handler, logger
from stroop_task.utils.marker import get_marker_writer

# Test this option
pyglet.options["win32_gdi_font"] = True


def run_paradigm(
    n_trials: int = 60,
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = True,  # allow overwriting this from cli for simple testing
    random_wait: bool = False,
):

    log_cfg = yaml.safe_load(open("./configs/logging.yaml"))
    log_path = Path(log_cfg["log_file"])
    log_path.parent.mkdir(exist_ok=True, parents=True)
    add_file_handler(log_path)
    logger.setLevel(log_cfg["level"])
    # Overwrite the config if needed
    if logger_level is not None:
        logger.setLevel(logger_level)

    mw = get_marker_writer(write_to_serial=write_to_serial)
    ctx = load_context(language=language, focus=focus, marker_writer=mw)
    ctx.add_window(
        pyglet.window.Window(
            fullscreen=ctx.fullscreen, height=ctx.screen_height, width=ctx.screen_width
        )
    )

    smgr = StroopTaskStateManager(ctx=ctx, random_wait=random_wait)

    # Hook up the drawing callback
    ctx.window.push_handlers(
        on_draw=partial(on_draw, ctx=ctx),
        on_key_press=partial(on_escape_exit_handler, ctx=ctx),
    )

    # Init
    ctx.create_stimuli(random_wait=random_wait)
    ctx.init_block_stimuli(n_trials)

    # Start running
    pyglet.clock.schedule_once(
        lambda dt: smgr.start_block(), 0.5
    )  # start after 0.5 sec

    try:
        pyglet.app.run()
    finally:
        ctx.close_context()


def run_paradigm_classical(
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = True,  # allow overwriting this from cli for simple testing
    random_wait: bool = False,
    classical_timeout_s: Optional[float] = None,
):
    """
    The arrangement and colors where drawn randomly once, but are then fixed
    """

    log_cfg = yaml.safe_load(open("./configs/logging.yaml"))
    log_path = Path(log_cfg["log_file"])
    log_path.parent.mkdir(exist_ok=True, parents=True)
    add_file_handler(log_path)
    logger.setLevel(log_cfg["level"])

    # Overwrite the config if needed
    if logger_level is not None:
        logger.setLevel(logger_level)

    mw = get_marker_writer(write_to_serial=write_to_serial)
    ctx = load_context(language=language, focus=focus, marker_writer=mw)
    ctx.add_window(
        pyglet.window.Window(
            fullscreen=ctx.fullscreen, height=ctx.screen_height, width=ctx.screen_width
        )
    )
    if classical_timeout_s:
        ctx.classical_timeout_s = classical_timeout_s
    smgr = StroopClassicTaskStateManager(ctx=ctx, random_wait=random_wait)

    # Hook up the drawing callback
    ctx.window.push_handlers(
        on_draw=partial(on_draw, ctx=ctx),
        on_key_press=partial(on_escape_exit_handler, ctx=ctx),
    )

    # Init
    ctx.create_stimuli(random_wait=random_wait)
    ctx.init_classical()

    # Start running
    pyglet.clock.schedule_once(
        lambda dt: smgr.start_block(), 0.5
    )  # start after 0.5 sec

    try:
        pyglet.app.run()
    finally:
        ctx.close_context()


def run_paradigm_cli(
    n_trials: int = 60,
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = False,  # allow overwriting this from cli for simple testing (which is what we usually have from serial)
    random_wait: bool = False,
    classical: bool = False,
    classic_stroop_time_s: float = 45,
):
    """Starting the Stroop paradigm standalone in a pyglet window

    Parameters
    ----------
    n_trials : int (default: 60)
        Number of trials to run in a block. Should be a multiple of 6 to ensure proper balancing

    language : str (default: "english")
        Language to use. Currently available:

            - "english"

            - "dutch"

            - "german"

    logger_level : str | None  (default: None)
        Configuration level for the logger. This will overwrite the value from `configs/logging.yaml`.
        Common python logging names are accepted: DEBUG, INFO, WARNING, ERROR

    focus : str (default: "color")
        Whether the task was to focus on `text` or on `color` for the upper word.
        Just used in logging. Currently not implemented! -> always focus on color

    write_to_serial : bool (default: False)
        If True, the marker writer will also consider the configuration for the serial output.
        Not used if no serial marker hardware is connected.

    random_wait : bool (default: False)
        If True, a random wait will be done between trials instead of waiting for the key down press. Timed as configured in `configs/task.yaml`.

    classical : bool (default: False)
        If True, the classical stroop paradigm will be run with displaying the color words
        on the screen as a table and the subject is asked to read as many as possible in
        a given time interval. Ask them to name the color of the font.

    classic_stroop_time_s : float (default: 45)
        Time in seconds for the classical stroop task. Used if `classical` is True.

    """

    if classical:
        run_paradigm_classical(
            language=language,
            logger_level=logger_level,
            focus=focus,
            write_to_serial=write_to_serial,
            random_wait=random_wait,
            classical_timeout_s=classic_stroop_time_s,
        )

    else:
        run_paradigm(
            n_trials=n_trials,
            language=language,
            logger_level=logger_level,
            focus=focus,
            write_to_serial=write_to_serial,
            random_wait=random_wait,
        )


def run_block_subprocess(**kwargs):
    kwargs_str = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
    cmd = "python -m stroop_task.main " + kwargs_str
    pid = Popen(cmd, shell=True)
    return pid


if __name__ == "__main__":
    Fire(run_paradigm_cli)
