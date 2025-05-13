# Needs to be Initialized once here as otherwise the init of the TkStroopContext is breaking
import tkinter as tk
from pathlib import Path

import yaml
from fire import Fire

win = tk.Tk()


def run_paradigm(
    n_trials: int = 6,
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = True,  # allow overwriting this from cli for simple testing
    random_wait: bool = False,
):

    from stroop_task.context_tk import load_tk_context
    from stroop_task.tk_task_manager import TkStroopTaskStateManager
    from stroop_task.utils.logging import add_file_handler, logger
    from stroop_task.utils.marker import get_marker_writer

    log_cfg = yaml.safe_load(open("./configs/logging.yaml"))
    log_path = Path(log_cfg["log_file"])
    log_path.parent.mkdir(exist_ok=True, parents=True)
    add_file_handler(log_path)
    logger.setLevel(log_cfg["level"])
    # Overwrite the config if needed
    if logger_level is not None:
        logger.setLevel(logger_level)

    mw = get_marker_writer(write_to_serial=write_to_serial)
    ctx = load_tk_context(language=language, focus=focus, marker_writer=mw, window=win)

    # ------------------------------------------------------------------------
    # Add window to context
    # ------------------------------------------------------------------------
    ctx.window.geometry("1920x1080")  # hard coded for now

    smgr = TkStroopTaskStateManager(ctx=ctx, random_wait=random_wait)

    # Init
    ctx.create_stimuli(random_wait=random_wait)
    ctx.init_block_stimuli(n_trials)

    ctx.window.after(500, smgr.start_block)

    try:
        ctx.window.mainloop()
    finally:
        ctx.close_context()


def run_paradigm_cli(
    n_trials: int = 6,
    language: str = "english",
    logger_level: str | None = "DEBUG",
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

    """

    if classical:
        raise NotImplementedError(
            "The classical Stroop task is not yet impleneted with the tkinter backend. Consider using the default pyglet version."
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


if __name__ == "__main__":

    n_trials: int = 6
    language: str = "english"
    logger_level: str | None = None
    focus: str = "color"
    write_to_serial: bool = False
    random_wait: bool = False

    Fire(run_paradigm_cli)
