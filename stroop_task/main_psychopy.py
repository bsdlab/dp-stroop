# A psychopy implementation of the stroop task

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from subprocess import Popen

from fire import Fire
from psychopy import clock, core, event, visual

from stroop_task.main import init_block_stimuli
from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter

# WORD_COLOR_PAIRS = [
#     ("red", (255, 0, 0, 255)),
#     ("blue", (0, 0, 255, 255)),
#     ("green", (0, 255, 0, 255)),
#     ("yellow", (255, 255, 0, 255)),
# ]

WORD_COLOR_PAIRS = [
    ("rot", (255, 0, 0, 255)),
    ("blau", (0, 0, 255, 255)),
    ("grün", (0, 255, 0, 255)),
    ("gelb", (255, 255, 0, 255)),
]

STARTBLOCK_MRK = 251
ENDBLOCK_MRK = 254
STARTTRIAL_MRK = 252
ENDTRIAL_MRK = 253
CONGRUENT_MRK = 1
INCONGRUENT_MRK = 2
REACTION_MRK = 3
TIMEOUT_MRK = 4


# A data structure for easier access
@dataclass
class Context:
    screen_ix: int = 0
    # screen_size: tuple[int, int] = (1680, 1050)
    screen_size: tuple[int, int] = (2600, 1450)
    fullscr: bool = False
    data_dir: Path = Path("./data/")
    script_dir: Path = Path("./stroop_task/")
    win_color: tuple[int, int, int] = (-1, -1, -1)

    reactions: list = field(default_factory=list)  # tracking
    block_stimuli: list = field(default_factory=list)
    known_stimuli: dict = field(default_factory=dict)
    lsl_outlet: object = None

    # parametrization
    stimulus_time_s: float = 2.0  # number of seconds to react
    pre_stimulus_time_s: float = 1.0  # time to show the fixation
    wait_time_min_s: float = 1.0  # random wait lower bound
    wait_time_max_s: float = 2.0  # random wait upper bound
    instruction_time_s: float = 5.0  # time to show the instructions

    def __init__(self):
        self.window = visual.Window(
            fullscr=self.fullscr,
            size=self.screen_size,
            units="norm",
            screen=self.screen_ix,
            color=self.win_color,
        )
        # marker writer
        self.marker_writer: MarkerWriter = MarkerWriter("COM4")


class StroopTaskStateManager:
    """
    Managing the stroop task, note: as opposed to the pyglet implementation
    this is not operating in state transitions, but simply in a loop
    """

    def __init__(
        self,
        ctx: Context,
        n_trials: int = 10,
        incongruent_fraction: float = 0.5,
        look_for_late_keys: bool = True,  # register late keys response
        flip: bool = True,
    ):
        logger.info("Initialising..")
        self.ctx = ctx
        self.n_trials = n_trials
        self.incongruent_fraction = incongruent_fraction
        self.look_for_late_keys = look_for_late_keys
        self.valid_keys = ["left", "right"]

        # some shorthands
        self.fixation = self.ctx.known_stimuli["fixation"]
        self.instructions = self.ctx.known_stimuli["instructions"]
        self.name = "stroop"
        # should be overwritten while running a block
        self.file_prefix = "STIM_UNKNOWN_"

        self.trial_clock = core.Clock()

        # to collect psychopy objects for drawing on the next flip
        self.frame = OrderedDict()

        self.reactions = []

        # data containers being used within the exec_block part
        logger.debug("initialised")

    def exec_block(
        self,
        block_nr: int = None,
        stim: str = None,
        block_config: dict = None,
    ) -> int:
        """
        Run a single block of the paradigm
        """

        self.send_marker(STARTBLOCK_MRK)
        self.file_prefix = (
            f"STIM_{stim}_" if stim is not None else "STIM_UNKNOWN_"
        )
        logger.debug(f">> Using {self.file_prefix=}")
        init_block_stimuli(self.n_trials, self.incongruent_fraction, self.ctx)

        self.show_instructions()
        time.sleep(self.ctx.instruction_time_s)

        # loop over stimuli in a single trial
        for stim_name, stim in self.ctx.block_stimuli:
            stim_mrk = (
                CONGRUENT_MRK
                if stim_name in [e[0] for e in WORD_COLOR_PAIRS]
                else INCONGRUENT_MRK
            )

            if (
                self.look_for_late_keys
            ):  # to disable after break --> no spurious late # noqa
                latekeys = event.getKeys(
                    self.valid_keys, timeStamped=self.trial_clock
                )

                if latekeys is not None:
                    for k, t in latekeys:
                        msg = f"Reaction-late {k}|{t}"
                        logger.info(msg)
                        self.reactions.append(msg)

                    latekeys = []

            self.clear_frame()
            event.clearEvents()
            tpre = core.getTime()

            # fixation phase
            self.send_marker(STARTTRIAL_MRK)
            self.frame["fixation"] = self.fixation
            self.draw_and_flip()
            core.wait(
                self.ctx.pre_stimulus_time_s,
                hogCPUperiod=self.ctx.pre_stimulus_time_s,
            )

            # stimulus
            self.clear_frame()
            self.frame["stimulus"] = stim
            # self.frame["photobox"] = self.ctx.knwown_stimuli["photobox"]['white']
            self.draw_and_flip()
            self.trial_clock.reset(newT=0.0)  # reset psychopy inner clock
            self.send_marker(stim_mrk)

            keys = event.waitKeys(
                self.ctx.stimulus_time_s, timeStamped=self.trial_clock
            )

            if keys is not None and keys != []:
                self.send_marker(REACTION_MRK)
                for k, t in keys:
                    msg = f"Reaction {k}|{t}"
                    logger.info(msg)
                    self.reactions.append(msg)
                keys = []

            else:
                self.send_marker(TIMEOUT_MRK)
                logger.info("No Reaction")

            # clear frame for random time
            self.clear_frame()
            self.draw_and_flip()

            self.send_marker(ENDTRIAL_MRK)

        # Clean-up
        self.send_marker(ENDBLOCK_MRK)

        return 0

    def show_instructions(self):
        self.clear_frame()
        self.frame["instructions"] = self.ctx.known_stimuli["instructions"]
        self.draw_and_flip()

    def draw_and_flip(self, exclude: list[str] = []):
        """Draws every element in the frame ict, excluding those
        passed in via exclude."""
        for element_name, element in self.frame.items():
            if element_name in exclude:
                continue
            else:
                element.draw()
        self.ctx.window.flip()

    def clear_frame(self):
        self.frame = OrderedDict()

    def send_marker(self, val):
        if isinstance(val, int) and val < 256:
            self.ctx.marker_writer.write(val)
        else:
            raise ValueError(
                "Please provide an int value < 256 to be written as a marker"
            )


# ----------------------------------------------------------------------------
#                      Initialization and cleanup
# ----------------------------------------------------------------------------


def close_context(ctx: Context):
    """Close the context stopping all pyglet elements"""
    ctx.window.close()


def create_stimuli(ctx: Context):
    """Create stimuli for the stroop task using WORD_COLOR_PAIRS"""

    stimuli = {
        "fixation": visual.TextStim(
            text="+",
            color=(255, 80, 80, 255),
            units="norm",
            pos=(0, 0),
            win=ctx.window,
        ),
        "instructions": visual.TextStim(
            # text="Please perform the stroop task `<` for incongruent, `>` for congruent",
            text="Farbe passt nicht zu Text: drücke `<-` \n\nFarbe passt: drücke `<-`",
            color=(250, 250, 250, 255),
            units="norm",
            win=ctx.window,
        ),
        "coherent": {
            cw: visual.TextStim(
                text=cw,
                color=cc,
                units="norm",
                pos=(0, 0),
                win=ctx.window,
            )
            for cw, cc in WORD_COLOR_PAIRS
        },
        "incoherent": {},
    }

    # permute the colors for the incorherent stimuli
    for cw, cc in WORD_COLOR_PAIRS:
        for cw2, cc2 in WORD_COLOR_PAIRS:
            if cw2 != cw:
                stimuli["incoherent"][f"{cw}_{cw2}"] = visual.TextStim(
                    text=cw,
                    color=cc2,
                    units="norm",
                    pos=(0, 0),
                    win=ctx.window,
                )

    # a rectangle used for a photodiode -> can be omitted if none are used
    # rect_white = visual.Rect(
    #     win=ctx.window, units="pix", size=(40, 40), fillColor=[1, 1, 1], pos=(0, 0)
    # )
    # rect_black = visual.Rect(
    #     win=ctx.window,
    #     units="pix",
    #     size=(40, 40),
    #     fillColor=[-1, -1, -1],
    # )
    #
    # rect_white.pos = (10, 500)  # (10, 510)  # (0, 520)
    # rect_black.pos = (10, 500)  # (10, 510)  # (0, 520)
    # stimuli["photobox"] = {"white": rect_white, "black": rect_black}

    ctx.known_stimuli = stimuli


def main(
    block_nr: int = 0,
    stim: str = "",
    n_trials: int = 10,
    incongruent_fraction: float = 0.5,
    logger_level: int = 20,
):
    if logger_level:
        logger.setLevel(logger_level)

    ctx = Context()
    create_stimuli(ctx)

    try:
        smgr = StroopTaskStateManager(
            ctx=ctx,
            n_trials=n_trials,
            incongruent_fraction=incongruent_fraction,
        )
        smgr.exec_block(
            block_nr=block_nr,
            stim=stim,
        )

    finally:
        close_context(ctx)


def run_block_subprocess(**kwargs):
    kwargs_str = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
    cmd = "python -m stroop_task.main_psychopy " + kwargs_str
    pid = Popen(cmd, shell=True)

    return pid


if __name__ == "__main__":
    Fire(main)
