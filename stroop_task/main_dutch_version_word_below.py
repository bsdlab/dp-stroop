# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial
from subprocess import Popen

import pyglet
from fire import Fire

from stroop_task.context import StroopContext
from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter


class StroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self, ctx: StroopContext):
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
        self.ctx.marker_writer.write(self.ctx.startblock_mrk, lsl_marker="start_block")
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
            self.ctx.marker_writer.write(self.ctx.endtrial_mrk, lsl_marker="end_trial")

    def show_fixation(self):
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]
        pyglet.clock.schedule_once(self.next_state, self.ctx.pre_stimulus_time_s)

    def show_stimulus(self):
        """Show the next stimulus in the self.ctx.block_stimuli list"""

        logger.debug(f"Showing stimulus {self.ctx.current_stimulus_idx}")

        # Go to end of block from here
        if self.ctx.current_stimulus_idx == len(self.ctx.block_stimuli):
            self.show_mean_reaction_time()
        else:
            logger.warning(
                f"Showing stimulus {self.ctx.current_stimulus_idx=}, {len(self.ctx.block_stimuli)=}"
            )
            cw_top, stim_top, cw_bot, stim_bot = self.ctx.block_stimuli[
                self.ctx.current_stimulus_idx
            ]

            # Move increment to end as otherwise stimulus at idx==0 is not shown
            correct_direction = "right" if cw_top == cw_bot else "left"
            logger.info(
                f"Showing stimulus {cw_top=}, {cw_bot=} (in white) - {correct_direction=}"
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
                self.ctx.congruent_mrk
                if cw_top in [e for e, _ in self.ctx.word_color_dict.items()]
                else self.ctx.incongruent_mrk
            )

            # Start showing stimuli (top only)
            self.ctx.current_stimuli = [stim_top]
            # add bottom after 100ms
            pyglet.clock.schedule_once(self.show_top_and_bottom_stimulus, delay=0.1)

            self.ctx.marker_writer.write(mrk, lsl_marker=f"{cw_top}|{stim_top}")

            # start taking time
            self.ctx.tic = time.perf_counter()

            # Set scheduled timeout << if it reaches here, we timed out
            pyglet.clock.schedule_once(self.register_timeout, self.ctx.stimulus_time_s)

    def show_top_and_bottom_stimulus(self, delay):
        cw_top, stim_top, cw_bot, stim_bot = self.ctx.block_stimuli[
            self.ctx.current_stimulus_idx
        ]
        self.ctx.current_stimuli = [stim_top, stim_bot]
        self.ctx.current_stimulus_idx += 1

    def register_timeout(self, dt):
        rtime_s = time.perf_counter() - self.ctx.tic
        self.ctx.reactions.append(("TIMEOUT", rtime_s))
        self.ctx.marker_writer.write(
            self.ctx.timeout_mrk, lsl_marker=f"timeout|{rtime_s=}"
        )
        logger.info(f"Reaction timeout: {rtime_s=}")
        self.ctx.window.pop_handlers()
        self.next_state()

    def random_wait(self):
        """
        Using the clock scheduler as sub ms accuracy is not needed anyways
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
            text=self.ctx.msgs["mean_reaction_time"] + f" {mean_reaction_time:.2f}s",
            color=(255, 255, 255, 255),
            font_size=self.ctx.font_size,
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
        self.ctx.marker_writer.write(self.ctx.endblock_mrk, lsl_marker="end_block")
        close_context(self.ctx)


# ----------------------------------------------------------------------------
#                      Initialization and cleanup
# ----------------------------------------------------------------------------


def close_context(ctx: StroopContext):
    """Close the context stopping all pyglet elements"""
    ctx.window.close()


def create_stimuli(ctx: StroopContext):
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
            text=ctx.msgs["instruction"],
            color=(255, 255, 255, 255),
            font_size=ctx.font_size,
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
                font_size=ctx.font_size,
                x=ctx.window.width / 2,
                y=ctx.window.height / 2,
                anchor_x="center",
                anchor_y="center",
            )
            for cw, cc in ctx.word_color_dict.items()
        },
        "neutral": {
            cw: pyglet.text.Label(
                text="XXXX",
                color=cc,
                font_size=ctx.font_size,
                x=ctx.window.width / 2,
                y=ctx.window.height / 2,
                anchor_x="center",
                anchor_y="center",
            )
            for cw, cc in ctx.word_color_dict.items()
        },
        "white": {
            cw: pyglet.text.Label(
                text=cw,
                color=(255, 255, 255, 255),
                font_size=ctx.font_size,
                x=ctx.window.width / 2,
                y=ctx.window.height / 2 - WHITE_Y_OFFSET_PX,
                anchor_x="center",
                anchor_y="center",
            )
            for cw, _ in ctx.word_color_dict.items()
        },
        "incoherent": {},
    }

    # permute the colors for the incorherent stimuli
    for cw, cc in ctx.word_color_dict.items():
        for cw2, cc2 in ctx.word_color_dict.items():
            if cw2 != cw:
                stimuli["incoherent"][f"{cw}_{cw2}"] = pyglet.text.Label(
                    text=cw,
                    color=cc2,
                    font_size=self.ctx.font_size,
                    x=ctx.window.width / 2,
                    y=ctx.window.height / 2,
                    anchor_x="center",
                    anchor_y="center",
                )

    ctx.known_stimuli = stimuli


def init_block_stimuli(n_trials: int, ctx: StroopContext):
    """Initialize a block of trials by modifying a context. The stimuli will
    be accessible in ctx.block_stimuli as list of tuples
    (word, pyglet.text.Label, pyglet.shapes.Rectangle, pyglet.shapes.Rectangle, str)
    The shapes are the squares that will be shown left and right of the word, while
    the final string indicates the correct direction

    Parameters
    ----------
    n_trials : int
        number of trials per block

    ctx: StroopContext
        the context to add to

    """
    # Using the full setup from here
    # https://www.sciencedirect.com/science/article/pii/S1053811900906657?via%3Dihub
    # 1/1/1 for congruent, incongruent, neutral
    # with lower word correct in 50% of the time

    assert n_trials % 6 == 0, (
        f"Please select {n_trials=} to be a multiple of 6 to allow for proper"
        " distrubution of congruent, incongruent, and neutral stimuli"
    )

    coherent_stimuli = ctx.known_stimuli["coherent"]
    incoherent_stimuli = ctx.known_stimuli["incoherent"]
    neutral_stimuli = ctx.known_stimuli["neutral"]
    white_stimuli = ctx.known_stimuli["white"]

    # create random sample by truncation
    top_stims = []
    for stim_dict in [coherent_stimuli, incoherent_stimuli, neutral_stimuli]:
        top_stims.extend(
            [
                (
                    (cw + "_XXXX", stim_dict[cw])
                    if stim_dict == neutral_stimuli
                    else (cw, stim_dict[cw])
                )
                for cw, stim in stim_dict.items()
                for _ in range(n_trials // 3)  # need to check for the incongruent case
            ][: n_trials // 3]
        )

    # Add bottom stims
    match_vect = [0, 1] * (n_trials // 2)
    random.shuffle(match_vect)

    stimuli = []
    for (cw_top, stim_top), match in zip(top_stims, match_vect):
        cwt = cw_top.split("_")[0]  # need to check for the incongruent case
        if match == 1:
            cw_bot = cwt
        else:
            cw_bot = random.choice([cw for cw in white_stimuli.keys() if cw != cw_top])

        stimuli.append((cw_top, stim_top, cw_bot, white_stimuli[cw_bot]))

    random.shuffle(stimuli)

    logger.debug(f"block stimuli: {stimuli}")
    ctx.block_stimuli = stimuli


# ----------------------------------------------------------------------------
#                            EVENT HANDLERS
# ----------------------------------------------------------------------------


def on_draw(ctx: StroopContext | None = None):
    ctx.window.clear()
    for stim in ctx.current_stimuli:
        stim.draw()


def on_key_press_handler(symbol, modifiers):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            close_context()


def on_key_press_stroop_reaction_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
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

        case pyglet.window.key.LEFT:
            # Potential logging and LSL here
            logger.debug("LEFT")
            handle_reaction("LEFT", ctx, smgr)


def handle_reaction(key: str, ctx: StroopContext, smgr: StroopTaskStateManager):
    """
    First track the time, then deactivate scheduled callbacks and manually
    trigger the next callback
    """
    rtime_s = (time.perf_counter - ctx.tic) / 1e9
    ctx.reactions.append((key, rtime_s))
    ctx.marker_writer.write(REACTION_MRK, lsl_marker=f"reaction_{key}|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")
    ctx.window.pop_handlers()
    # Remove the scheduled timeout callback because we trigger the next state directly
    pyglet.clock.unschedule(smgr.register_timeout)

    # trigger next state
    smgr.next_state()


def instruction_skip_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Skip the instructions and start the block"""
    match symbol:
        case pyglet.window.key.SPACE:
            logger.debug("User finished instructions")
            ctx.window.pop_handlers()
            pyglet.clock.unschedule(smgr.show_fixation)
            smgr.show_fixation()


def run_paradigm(
    n_trials: int = 6,
    logger_level: str | None = None,
    focus: str = "text",
    debug_marker_writer: bool = False,
):
    # Overwrite the config if needed
    if logger_level is not None:
        logger.setLevel(logger_level)

    ctx = StroopContext(focus=focus)
    window: pyglet.window.BaseWindow = pyglet.window.Window(height=500, width=800)
    ctx.add_window(window)

    smgr = StroopTaskStateManager(ctx=ctx)

    # Hook up the drawing callback
    pon_draw = partial(on_draw, ctx=ctx)
    ctx.window.push_handlers(on_draw=pon_draw)

    # Init
    create_stimuli(ctx)
    init_block_stimuli(n_trials, ctx)
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
