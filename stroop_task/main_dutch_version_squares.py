# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial
from subprocess import Popen

import pyglet
from fire import Fire

from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter

# from utils.logging import logger
# from utils.marker import MarkerWriter

WORD_COLOR_PAIRS = [
    ("rood", (255, 0, 0, 255)),
    ("blauw", (0, 0, 255, 255)),
    ("groen", (0, 255, 0, 255)),
    ("geel", (255, 255, 0, 255)),
]

# Reduced set of markers for the Maastricht setup
STARTBLOCK_MRK = 64  # 251
ENDBLOCK_MRK = 64  # 254
STARTTRIAL_MRK = 2  # 252
ENDTRIAL_MRK = 4  # 253
CONGRUENT_MRK = 0  # 1
INCONGRUENT_MRK = 0  # 2
REACTION_MRK = 16  # 3
TIMEOUT_MRK = 16  # 4

SQUARE_WIDTH = 200


# A data structure for easier access
@dataclass
class Context:
    window: pyglet.window.Window = pyglet.window.Window(height=500, width=800)
    window.set_fullscreen(False)
    reactions: list = field(default_factory=list)  # tracking
    block_stimuli: list = field(default_factory=list)
    known_stimuli: dict = field(default_factory=dict)
    lsl_outlet: object = None
    current_stimulus_idx: int = 0  # will be used to index block stimuli
    current_stimuli: list[pyglet.text.Label, pyglet.shapes.Rectangle] = field(
        default_factory=list
    )  # tracking stimuli for drawing

    # parametrization
    stimulus_time_s: float = 2.0  # number of seconds to react
    pre_stimulus_time_s: float = 1.0  # time to show the fixation
    wait_time_min_s: float = 1.0  # random wait lower bound
    wait_time_max_s: float = 2.0  # random wait upper bound
    instruction_time_s: float = (
        1000.0  # time to show the instructions, basically show until key press
    )
    results_show_time_s: float = 5.0  # time to show the results

    # time keeping
    tic: int = 0
    marker_writer: MarkerWriter | None = None
    focus: str = (
        "text"  # can be `text` or `color` (font color), determines which would be considered as correct
    )

    # marker writer
    def __post_init__(self):
        self.marker_writer: MarkerWriter = MarkerWriter("COM9")
        self.marker_writer.serial_write = self.marker_writer.utf8_write


class StroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self, ctx: Context):
        self.ctx = ctx  # the context under which to operate
        self.current_state: str = "fixation"  # starting with fixation

        # This list of states also orders how stimuli will appear
        self.states: list = ["fixation", "stimulus", "wait"]
        self.transition_map: dict = {
            "fixation": self.show_fixation,
            "stimulus": self.show_stimulus,
            "wait": self.random_wait,
        }

    def start_block(self):
        """Start a block of trials"""

        logger.debug("Showing intructions")
        self.ctx.marker_writer.write(STARTBLOCK_MRK, lsl_marker="start_block")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["instructions"]]

        # Add handler to skip on space press
        self.ctx.window.push_handlers(
            on_key_press=partial(
                instruction_skip_handler,
                ctx=self.ctx,
                smgr=self,
            )
        )

        # transition to show fixation, which will then start the state
        # transitions
        pyglet.clock.schedule_once(
            lambda dt: self.show_fixation(), self.ctx.instruction_time_s
        )

    def next_state(self, dt=0.0):
        """
        Transition to the next state. dt is only for compliance with pyglet
        callback signature
        """
        curr_i = self.states.index(self.current_state)
        next_i = (curr_i + 1) % len(self.states)
        next_state = self.states[next_i]
        logger.debug(f"Transitioning from `{self.current_state}` to " f"`{next_state}`")
        self.current_state = next_state
        self.transition_map[next_state]()
        if next_state == "fixation":
            self.ctx.marker_writer.write(ENDTRIAL_MRK, lsl_marker="end_trial")

    def show_fixation(self):
        self.ctx.marker_writer.write(STARTTRIAL_MRK, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]
        pyglet.clock.schedule_once(self.next_state, self.ctx.pre_stimulus_time_s)

    def show_stimulus(self):
        """Show the next stimulus in the self.ctx.block_stimuli list"""

        logger.debug(f"Showing stimulus {self.ctx.current_stimulus_idx}")

        # Go to end of block from here
        if self.ctx.current_stimulus_idx == len(self.ctx.block_stimuli):
            self.show_mean_reaction_time()
        else:
            stim_name, stim_label, square_left, square_right, correct_direction = (
                self.ctx.block_stimuli[self.ctx.current_stimulus_idx]
            )

            # Move increment to end as otherwise stimulus at idx==0 is not shown
            self.ctx.current_stimulus_idx += 1

            logger.info(
                f"Showing stimulus {stim_name=}, left_square={square_left.color}, "
                f"right_square={square_right.color} - {correct_direction=}"
            )

            # Starting to listen to keyboard input
            self.ctx.window.push_handlers(
                on_key_press=partial(
                    on_key_press_stroop_reaction_handler,
                    ctx=self.ctx,
                    smgr=self,
                )
            )

            mrk = (
                CONGRUENT_MRK
                if stim_name in [e[0] for e in WORD_COLOR_PAIRS]
                else INCONGRUENT_MRK
            )

            # Start showing stimuli
            self.ctx.current_stimuli = [stim_label, square_left, square_right]
            self.ctx.marker_writer.write(mrk, lsl_marker=f"{stim_name}|{stim_label}")

            # start taking time
            self.ctx.tic = time.perf_counter_ns()

            # Set scheduled timeout << if it reaches here, we timed out
            pyglet.clock.schedule_once(self.register_timeout, self.ctx.stimulus_time_s)

    def register_timeout(self, dt):
        rtime_s = (time.perf_counter_ns() - self.ctx.tic) / 1e9
        self.ctx.reactions.append(("TIMEOUT", rtime_s))
        self.ctx.marker_writer.write(TIMEOUT_MRK, lsl_marker="timeout|{rtime_s=}")
        logger.info(f"Reaction timeout: {rtime_s=}")
        self.ctx.window.pop_handlers()
        self.next_state()

    def random_wait(self):
        """
        Using the clock scheduler as sub ms accuracy is not needed anyways
        TODO: Benchmark accurarcy of the clock scheduler
        """
        self.ctx.current_stimuli = []
        pyglet.clock.schedule_once(
            self.next_state,
            random.uniform(self.ctx.wait_time_min_s, self.ctx.wait_time_max_s),
        )

    def show_mean_reaction_time(self):
        logger.info(f"Reaction_times={self.ctx.reactions}")
        mean_reaction_time = sum([e[1] for e in self.ctx.reactions]) / len(
            self.ctx.reactions
        )
        text = pyglet.text.Label(
            # text="Please perform the stroop task `<` for incongruent, `>` for"
            # " congruent",
            text=f"Je gemiddelde reactietijd is: {mean_reaction_time:.2f}s",
            color=(255, 255, 255, 255),
            font_size=36,
            x=self.ctx.window.width / 2,
            y=self.ctx.window.height / 2,
            anchor_x="center",
            anchor_y="center",
            width=self.ctx.window.width * 0.8,
        )

        self.ctx.current_stimuli = [text]

        pyglet.clock.schedule_once(
            lambda dt: self.end_block(), self.ctx.results_show_time_s
        )

    def end_block(self):
        """End the block and log the results"""

        logger.debug("Ending block")

        # Display average reaction time

        logger.info(f"{self.ctx.reactions}")
        self.ctx.marker_writer.write(ENDBLOCK_MRK, lsl_marker="end_block")
        close_context(self.ctx)


# ----------------------------------------------------------------------------
#                      Initialization and cleanup
# ----------------------------------------------------------------------------


def close_context(ctx: Context):
    """Close the context stopping all pyglet elements"""
    ctx.window.close()


def create_stimuli(ctx: Context):
    """Create stimuli for the stroop task using WORD_COLOR_PAIRS"""

    stimuli = {
        "fixation": pyglet.text.Label(
            text="+",
            color=(80, 80, 80, 255),
            font_size=56,
            x=ctx.window.width / 2,
            y=ctx.window.height / 2,
            anchor_x="center",
            anchor_y="center",
        ),
        "instructions": pyglet.text.Label(
            # text="Please perform the stroop task `<` for incongruent, `>` for"
            # " congruent",
            text="Bedankt voor uw deelname aan deze taak. Kijk naar de gekleurde woorden."
            "\n"
            " Als woordbetekenis en kleur NIET overeenkomen druk dan op `<`."
            "\n"
            " Als woordbetekenis en kleur overeenkomen druk dan op `>` ."
            "\n"
            "Druk op spatie om te starten",
            color=(255, 255, 255, 255),
            font_size=36,
            x=ctx.window.width / 2,
            y=ctx.window.height / 2,
            anchor_x="center",
            anchor_y="center",
            width=ctx.window.width * 0.8,
            multiline=True,
        ),
        "coherent": {
            cw: pyglet.text.Label(
                text=cw,
                color=cc,
                font_size=36,
                x=ctx.window.width / 2,
                y=ctx.window.height / 2,
                anchor_x="center",
                anchor_y="center",
            )
            for cw, cc in WORD_COLOR_PAIRS
        },
        "incoherent": {},
    }

    # permute the colors for the incorherent stimuli
    for cw, cc in WORD_COLOR_PAIRS:
        for cw2, cc2 in WORD_COLOR_PAIRS:
            if cw2 != cw:
                stimuli["incoherent"][f"{cw}_{cw2}"] = pyglet.text.Label(
                    text=cw,
                    color=cc2,
                    font_size=36,
                    x=ctx.window.width / 2,
                    y=ctx.window.height / 2,
                    anchor_x="center",
                    anchor_y="center",
                )

    # add the squares in each color left and right positioned
    for pos in ["left", "right"]:
        for cw, cc in WORD_COLOR_PAIRS:
            stimuli["rect_" + cw + "_" + pos] = pyglet.shapes.Rectangle(
                x=(
                    ctx.window.width / 2
                    - (
                        200 + SQUARE_WIDTH
                    )  # x is always the left edge position -> adding the width
                    if pos == "left"
                    else ctx.window.width / 2 + 200
                ),
                y=ctx.window.height / 2 - 300,
                width=SQUARE_WIDTH,
                height=SQUARE_WIDTH,
                color=cc,
            )

    ctx.known_stimuli = stimuli


def init_block_stimuli(n_trials: int, incoherent_fraction: float, ctx: Context):
    """Initialize a block of trials by modifying a context. The stimuli will
    be accessible in ctx.block_stimuli as list of tuples
    (word, pyglet.text.Label, pyglet.shapes.Rectangle, pyglet.shapes.Rectangle, str)
    The shapes are the squares that will be shown left and right of the word, while
    the final string indicates the correct direction

    Parameters
    ----------
    n_trials : int
        number of trials per block

    incoherent_fraction : float
        fraction of incoherent trials within n_trials. Will be rounded down
        to next integer value
    ctx: Context
        the context to add to

    """
    # Prepare the stimuli
    n_incoherent = int(incoherent_fraction * n_trials)
    n_coherent = n_trials - n_incoherent

    assert n_incoherent % 2 == 0 and n_coherent % 2 == 0, (
        f"Please select {n_trials=} and {incoherent_fraction=} such that the"
        f" resulting {n_incoherent=} and {n_coherent=} are even numbers. This"
        " is relevant to balance the correct directions."
    )

    coherent_stimuli = ctx.known_stimuli["coherent"]
    incoherent_stimuli = ctx.known_stimuli["incoherent"]

    # incoherent stims
    correct_direction = ["left"] * (n_incoherent // 2) + ["right"] * (n_incoherent // 2)
    random.shuffle(correct_direction)
    stimuli_ic = []
    for i, cw in enumerate(
        random.choices(list(incoherent_stimuli.keys()), k=n_incoherent)
    ):
        correct_dir = correct_direction[i]
        other_dir = "right" if correct_dir == "left" else "left"
        if ctx.focus == "text":
            corr = ctx.known_stimuli[f"rect_{cw.split("_")[0]}_{correct_dir}"]
            incorr = ctx.known_stimuli[f"rect_{cw.split('_')[1]}_{other_dir}"]
        elif ctx.focus == "color":
            corr = ctx.known_stimuli[f"rect_{cw.split("_")[1]}_{correct_dir}"]
            incorr = ctx.known_stimuli[f"rect_{cw.split('_')[0]}_{other_dir}"]
        else:
            raise ValueError(f"Invalid {ctx.focus=}, should be `text` or `color`")

        sq_left, sq_right = (corr, incorr) if correct_dir == "left" else (incorr, corr)

        stimuli_ic.append(
            (cw, incoherent_stimuli[cw], sq_left, sq_right, correct_direction[i])
        )

    # coherent stims
    correct_direction = ["left"] * (n_incoherent // 2) + ["right"] * (n_incoherent // 2)
    random.shuffle(correct_direction)
    stimuli_c = []
    for i, cw in enumerate(random.choices(list(coherent_stimuli.keys()), k=n_coherent)):
        correct_dir = correct_direction[i]
        other_dir = "right" if correct_dir == "left" else "left"

        corr = ctx.known_stimuli[f"rect_{cw}_{correct_dir}"]
        icw = random.choices(
            [colorword for colorword in coherent_stimuli.keys() if colorword != cw], k=1
        )[0]

        incorr = ctx.known_stimuli[f"rect_{icw}_{other_dir}"]

        sq_left, sq_right = (corr, incorr) if correct_dir == "left" else (incorr, corr)

        stimuli_c.append(
            (cw, coherent_stimuli[cw], sq_left, sq_right, correct_direction[i])
        )

    stimuli = stimuli_ic + stimuli_c

    random.shuffle(stimuli)

    logger.debug(f"block stimuli: {stimuli}")
    ctx.block_stimuli = stimuli


# ----------------------------------------------------------------------------
#                            EVENT HANDLERS
# ----------------------------------------------------------------------------


def on_draw(ctx: Context | None = None):
    ctx.window.clear()
    for stim in ctx.current_stimuli:
        stim.draw()


def on_key_press_handler(symbol, modifiers):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            close_context()


def on_key_press_stroop_reaction_handler(
    symbol, modifiers, ctx: Context, smgr: StroopTaskStateManager
):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            close_context()
        case pyglet.window.key.RIGHT:
            # Potential logging and LSL here
            logger.debug("RIGHT")
            handle_reaction("RIGHT", ctx, smgr)
            # breaking of by skipping scheduled manager evctx
        case pyglet.window.key.LEFT:
            # Potential logging and LSL here
            logger.debug("LEFT")
            handle_reaction("LEFT", ctx, smgr)


def handle_reaction(key: str, ctx: Context, smgr: StroopTaskStateManager):
    """
    First track the time, then deactivate scheduled callbacks and manually
    trigger the next callback
    """
    rtime_s = (time.perf_counter_ns() - ctx.tic) / 1e9
    ctx.reactions.append((key, rtime_s))
    ctx.marker_writer.write(REACTION_MRK, lsl_marker=f"reaction_{key}|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")
    ctx.window.pop_handlers()
    # Remove the scheduled timeout callback because we trigger the next state directly
    pyglet.clock.unschedule(smgr.register_timeout)

    # trigger next state
    smgr.next_state()


def instruction_skip_handler(
    symbol, modifiers, ctx: Context, smgr: StroopTaskStateManager
):
    """Skip the instructions and start the block"""
    match symbol:
        case pyglet.window.key.SPACE:
            logger.debug("User finished instructions")
            ctx.window.pop_handlers()
            pyglet.clock.unschedule(smgr.show_fixation)
            smgr.show_fixation()


def run_paradigm(
    n_trials: int = 4,
    incoherent_fraction: float = 0.5,
    logger_level: int = 10,
    focus: str = "text",
):
    if logger_level:
        logger.setLevel(logger_level)

    ctx = Context(focus=focus)

    smgr = StroopTaskStateManager(ctx=ctx)

    # Hook up the drawing callback
    pon_draw = partial(on_draw, ctx=ctx)
    ctx.window.push_handlers(on_draw=pon_draw)

    # Init
    create_stimuli(ctx)
    init_block_stimuli(n_trials, incoherent_fraction, ctx)
    # Start running
    pyglet.clock.schedule_once(lambda dt: smgr.start_block(), 0.5)  # start after 1 sec
    try:
        pyglet.app.run()
    finally:
        close_context(ctx)


def run_block_subprocess(**kwargs):
    kwargs_str = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
    cmd = "python -m stroop_task.main_dutch_version_squares " + kwargs_str
    pid = Popen(cmd, shell=True)
    return pid


if __name__ == "__main__":
    Fire(run_paradigm)
