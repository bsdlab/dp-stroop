# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from subprocess import Popen

import pyglet
import yaml
from fire import Fire

from stroop_task.context import StroopContext, load_context
from stroop_task.utils.logging import add_file_handler, logger
from stroop_task.utils.marker import get_marker_writer


class StroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self, ctx: StroopContext, random_wait: bool = False):
        self.ctx = ctx  # the context under which to operate

        # This list of states also orders how stimuli will appear
        self.transition_map: dict = {
            "fixation": self.show_fixation,
            "fixation_until_arrow_down": self.show_fixation_until_arrow_down,
            "stimulus": self.show_stimulus,
            "random_wait": self.random_wait,
        }
        self.next_state_transition: None = None

        if random_wait:
            self.states: list = ["random_wait", "fixation", "stimulus"]
        # waiting for key_press and release of the down arrow
        else:
            self.states: list = ["fixation_until_arrow_down", "stimulus"]

        self.current_state: str = self.states[0]  # starting with fixation

        # auxiliary for down press
        self.down_pressed = False

    def start_block(self):
        """Start a block of trials"""

        logger.debug("Showing intructions")
        self.ctx.marker_writer.write(self.ctx.startblock_mrk, lsl_marker="start_block")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["instruction_batch"]]

        # Add handler to skip on space press
        self.ctx.window.push_handlers(
            on_key_press=partial(
                instruction_skip_handler,
                ctx=self.ctx,
                smgr=self,
            )
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

        if next_state.startswith("fixation"):
            self.ctx.marker_writer.write(self.ctx.endtrial_mrk, lsl_marker="end_trial")

    def show_fixation(self):
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]

        # transition to key press
        pyglet.clock.schedule_once(self.next_state, self.ctx.pre_stimulus_time_s)

    def show_fixation_until_arrow_down(self):
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]

        self.ctx.window.push_handlers(
            on_key_press=partial(
                on_key_press_down,  # this will trigger the transition if ready
                ctx=self.ctx,
                smgr=self,
            ),
            on_key_release=partial(
                on_key_release_down,
                smgr=self,
            ),
        )

    def show_stimulus(self):
        """Show the next stimulus in the self.ctx.block_stimuli list"""

        # Go to end of block from here
        if self.ctx.current_stimulus_idx == len(self.ctx.block_stimuli):
            self.show_mean_reaction_time()
        else:
            logger.debug(
                f"Showing stimulus {self.ctx.current_stimulus_idx=} of {len(self.ctx.block_stimuli)}"
            )
            cw_top, stim_top, cw_bot, stim_bot = self.ctx.block_stimuli[
                self.ctx.current_stimulus_idx
            ]

            # Move increment to end as otherwise stimulus at idx==0 is not shown
            correct_direction = "right" if cw_top == cw_bot else "left"
            logger.info(
                f"Showing stimulus {cw_top=}, {cw_bot=} (in white) - {correct_direction=}"
            )

            # pop all other handlers but the first layer (containing the on_draw and exit)
            while len(self.ctx.window._event_stack) > 1:
                self.ctx.window.pop_handlers()

            self.ctx.window.push_handlers(
                on_key_press=partial(
                    on_key_press_stroop_reaction_handler,
                    ctx=self.ctx,
                    smgr=self,
                ),
                on_key_release=partial(
                    on_key_release_log_onset, ctx=self.ctx, smgr=self
                ),
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
        self.ctx.window.remove_handlers("on_key_press")
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
            x=self.ctx.window.width // 2,
            y=self.ctx.window.height // 2,
            anchor_x="center",
            anchor_y="center",
            width=self.ctx.window.width * 0.8,
            multiline=True,
        )

        self.ctx.current_stimuli = [text]

        pyglet.clock.schedule_once(
            lambda dt: self.end_block(), self.ctx.results_show_time_s
        )

    def end_block(self):
        """End the block and log the results"""

        logger.debug("Ending block")

        # Display average reaction time
        logger.info(f"Reactions {self.ctx.reactions}")
        self.ctx.marker_writer.write(self.ctx.endblock_mrk, lsl_marker="end_block")
        self.ctx.close_context()


# ----------------------------------------------------------------------------
#                      Handlers
# ----------------------------------------------------------------------------


def on_draw(ctx: StroopContext):
    ctx.window.clear()
    for stim in ctx.current_stimuli:
        stim.draw()


def on_escape_exit_handler(symbol, modifiers, ctx: StroopContext):
    """The basic escape handler"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            ctx.close_context()


def on_key_press_stroop_reaction_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.RIGHT:
            # Potential logging and LSL here
            logger.info("RIGHT pressed")
            handle_reaction("RIGHT", ctx, smgr)
            # breaking of by skipping scheduled manager evctx
        case pyglet.window.key.LEFT:
            # Potential logging and LSL here
            logger.info("LEFT pressed")
            handle_reaction("LEFT", ctx, smgr)


def handle_reaction(key: str, ctx: StroopContext, smgr: StroopTaskStateManager):
    """
    First track the time, then deactivate scheduled callbacks and manually
    trigger the next callback
    """
    rtime_s = time.perf_counter() - ctx.tic
    ctx.reactions.append((key, rtime_s))
    ctx.marker_writer.write(ctx.reaction_mrk, lsl_marker=f"reaction_{key}|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")

    # never pop last layer
    while len(ctx.window._event_stack) > 1:
        ctx.window.pop_handlers()

    # Remove the scheduled timeout callback because we trigger the next state directly
    pyglet.clock.unschedule(smgr.register_timeout)

    # trigger next state
    smgr.next_state()


def on_key_press_down(
    symbol, modifier, ctx: StroopContext, smgr: StroopTaskStateManager
):
    if symbol == pyglet.window.key.DOWN and not smgr.down_pressed:
        # start tracking
        smgr.down_pressed = True
        logger.info("Arrow down pressed")
        pyglet.clock.unschedule(
            smgr.next_state
        )  # ensure that only one transition is every triggered
        pyglet.clock.schedule_once(smgr.next_state, ctx.arrow_down_press_to_continue_s)


def on_key_release_down(symbol, modifier, smgr: StroopTaskStateManager):
    match symbol:
        case pyglet.window.key.DOWN:
            # if this happens reset the timer --> so stop the transition
            smgr.down_pressed = False
            pyglet.clock.unschedule(smgr.next_state)


def on_key_release_log_onset(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    match symbol:
        case pyglet.window.key.DOWN:
            smgr.down_pressed = False
            logger.info("Arrow down released")
            ctx.marker_writer.write(
                ctx.lift_off_mrk, lsl_marker="reaction onset by down key lift off"
            )


def instruction_skip_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Skip the instructions and start the block"""
    match symbol:
        case pyglet.window.key.SPACE:
            logger.info("User finished instructions")
            # never pop last layer
            while len(ctx.window._event_stack) > 1:
                ctx.window.pop_handlers()

            pyglet.clock.unschedule(smgr.show_fixation)
            smgr.transition_map[smgr.current_state]()


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


def run_paradigm_cli(
    n_trials: int = 60,
    language: str = "english",
    logger_level: str | None = None,
    focus: str = "color",
    write_to_serial: bool = False,  # allow overwriting this from cli for simple testing (which is what we usually have from serial)
    random_wait: bool = False,
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

    """
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
