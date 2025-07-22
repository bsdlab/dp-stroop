from subprocess import Popen

from fire import Fire

from stroop_task.main import run_paradigm_cli
from stroop_task.utils.logging import logger

# This is used for integrating with the Dareplane server and just wrapping around
# the CLI version. It is replicated here to keep the CLI usage from main untouched.


def run_paradigm(**kwargs):
    """
    Wrapping around the `stroop_task.main.run_paradigm_cli`.
    Starting the Stroop paradigm standalone in a pyglet window

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
    run_paradigm_cli(**kwargs)


def run_block_subprocess(**kwargs):
    kwargs_str = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
    cmd = "python -m stroop_task.run_subprocess " + kwargs_str
    logger.info(f"Starting subprocess with command: {cmd}")
    pid = Popen(cmd, shell=True)

    return pid


if __name__ == "__main__":
    Fire(run_paradigm)
