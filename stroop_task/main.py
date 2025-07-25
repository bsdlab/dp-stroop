# A pyglet implementation of the stroop task

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


def run_paradigm(
    n_trials: int = 60,
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = True,  # allow overwriting this from cli for simple testing
    random_wait: bool = False,
    show_fps: bool = False,
    tutorial_mode: bool = False,
):
    """
    Run the two-word Stroop task paradigm.

    This function sets up and runs the two-word Stroop task paradigm using the Pyglet library.
    It initializes the logging configuration, creates the context for the Stroop task,
    sets up the window, and manages the task state. The function also adds the
    drawing callbacks and starts the task after a short delay.

    Parameters
    ----------
    n_trials : int, optional
        The number of trials to run in a block - needs to be an integer divisible by 6 for balancing. Default is 60.
    language : str, optional
        The language setting for the Stroop task. Default is "english".
    logger_level : str | None, optional
        The logging level to set for the logger. If None, the level from the
        configuration file is used. Default is None.
    focus : str, optional
        The focus of the task, either "text" or "color". Default is "color".
    write_to_serial : bool, optional
        Whether to write markers to a serial port. Default is True.
    random_wait : bool, optional
        Whether to use a random wait between trials. Default is False. If false, the user is required
        to push the arrow-down button for at least 500ms to start the next trial. If true, a random
        inter-trial-interval will be used. See `configs/task.yaml` and the `wait_time_min_s` and `wait_time_max_s` values therein.
    show_fps : bool, optional
        Whether to show the frames per second (FPS) on the screen. Default is False.
    tutorial_mode: bool, optional
        Whether to run the task in tutorial mode. Default is False. If true, the timeout for
        reaction is increased to 60s

    Returns
    -------
    None
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

    if tutorial_mode:
        ctx.stimulus_time_s = 60

    config = pyglet.gl.Config(double_buffer=True, depth_size=16)
    ctx.add_window(
        pyglet.window.Window(
            fullscreen=ctx.fullscreen,
            height=ctx.screen_height,
            width=ctx.screen_width,
            vsync=False,
            config=config,
        )
    )

    smgr = StroopTaskStateManager(ctx=ctx, random_wait=random_wait)

    fps_display = (
        pyglet.window.FPSDisplay(window=ctx.window, color=(255, 255, 255, 255))
        if show_fps
        else None
    )

    # Hook up the drawing callback
    ctx.window.push_handlers(
        on_draw=partial(on_draw, ctx=ctx, fps_display=fps_display),
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
    show_fps: bool = False,
    block_nr: int = 1,
    no_audio: bool = False,
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
    ctx = load_context(
        language=language,
        focus=focus,
        marker_writer=mw,
        block_nr=block_nr,
        no_audio=no_audio,
    )

    config = pyglet.gl.Config(double_buffer=True, depth_size=16)
    ctx.add_window(
        pyglet.window.Window(
            fullscreen=ctx.fullscreen,
            height=ctx.screen_height,
            width=ctx.screen_width,
            vsync=False,
            config=config,
        )
    )
    if classical_timeout_s:
        ctx.classical_timeout_s = classical_timeout_s
    smgr = StroopClassicTaskStateManager(
        ctx=ctx, random_wait=random_wait, no_audio=no_audio
    )

    fps_display = (
        pyglet.window.FPSDisplay(window=ctx.window, color=(255, 255, 255, 255))
        if show_fps
        else None
    )

    # Hook up the drawing callback
    ctx.window.push_handlers(
        on_draw=partial(on_draw, ctx=ctx, fps_display=fps_display),
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
    show_fps: bool = False,
    block_nr: int = 1,
    no_audio: bool = False,
    tutorial_mode: bool = False,
):
    """Starting the Stroop paradigm standalone in a pyglet window

    Parameters
    ----------
    n_trials : int (default: 60)
        Number of trials to run in a block. Should be a multiple of 12 to ensure proper balancing

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

    show_fps: bool
        If True, the FPS will be shown on the screen.

    block_nr : int (default: 1)
        The block number of the current run. This is used as a seed for the
        classical Stroop task's random generator -> allows to generate new
        layouts in case more than one block is used.

    no_audio : bool (default: False)
        If True, no audio will be recorded.

    tutorial_mode : bool (default: False)
        If True, the tutorial mode will be used for the modified Stroop task
        increasing the timeout to 60s.

    """

    if classical:
        run_paradigm_classical(
            language=language,
            logger_level=logger_level,
            focus=focus,
            write_to_serial=write_to_serial,
            random_wait=random_wait,
            classical_timeout_s=classic_stroop_time_s,
            show_fps=show_fps,
            block_nr=block_nr,
            no_audio=no_audio,
        )

    else:
        run_paradigm(
            n_trials=n_trials,
            language=language,
            logger_level=logger_level,
            focus=focus,
            write_to_serial=write_to_serial,
            random_wait=random_wait,
            show_fps=show_fps,
            tutorial_mode=tutorial_mode,
        )


if __name__ == "__main__":
    logger.handlers.pop()  # popping off the UJsonLogger from dareplane_utils
    Fire(run_paradigm_cli)
