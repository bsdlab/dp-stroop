import random
import time
from functools import partial

import pyglet

from stroop_task.context import StroopContext, load_context
from stroop_task.custom_eventloop import MyEventLoop
from stroop_task.utils.logging import add_file_handler, logger


class StroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self, ctx: StroopContext, random_wait: bool = False):
        self.ctx = ctx  # the context under which to operate
        self.evloop: MyEventLoop = MyEventLoop(window=ctx.window)

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
        self.on_key_press_handler: partial | None = None
        self.on_key_release_handler: partial | None = None

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

    def next_state(self):
        """
        Transition to the next state
        """
        curr_i = self.states.index(self.current_state)
        next_i = (curr_i + 1) % len(self.states)
        next_state = self.states[next_i]
        logger.debug(f"Transitioning from `{self.current_state}` to " f"`{next_state}`")
        self.current_state = next_state

        if next_state.startswith("fixation"):
            self.ctx.marker_writer.write(self.ctx.endtrial_mrk, lsl_marker="end_trial")

        self.transition_map[next_state]()

    def show_fixation(self):
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]

        # transition to key press
        self.evloop.add_delayed_callback_once(
            cb=self.next_state, dt=self.ctx.pre_stimulus_time_s
        )

    def show_fixation_until_arrow_down(self):
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]

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
            if self.ctx.focus == "color":
                correct_direction = (
                    "right" if cw_top.split("_")[1] == cw_bot else "left"
                )
            elif self.ctx.focus == "text":
                correct_direction = (
                    "right" if cw_top.split("_")[0] == cw_bot else "left"
                )
            else:
                raise ValueError(f"Unknown {self.ctx.focus=}")

            logger.info(
                f"Showing stimulus {cw_top=}, {cw_bot=} (in white) - {correct_direction=}"
            )

            mrk = (
                self.ctx.congruent_mrk
                if cw_top in [e for e, _ in self.ctx.word_color_dict.items()]
                else self.ctx.incongruent_mrk
            )

            # Start showing stimuli (top only)
            self.ctx.current_stimuli = [stim_top]
            # add bottom after 100ms
            self.evloop.add_delayed_callback_once(
                cb=self.show_top_and_bottom_stimulus, dt=0.1
            )

            self.ctx.marker_writer.write(mrk, lsl_marker=f"{cw_top}|{stim_top}")

            # start taking time
            self.ctx.tic = time.perf_counter()

            # Set scheduled timeout << if it reaches here, we timed out
            #
            self.evloop.add_delayed_callback_once(
                cb=self.register_timeout, dt=self.ctx.stimulus_time_s
            )

    def show_top_and_bottom_stimulus(self):
        cw_top, stim_top, cw_bot, stim_bot = self.ctx.block_stimuli[
            self.ctx.current_stimulus_idx
        ]
        self.ctx.current_stimuli = [stim_top, stim_bot]
        self.ctx.current_stimulus_idx += 1

    def register_timeout(self):
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

        # remove the on_key_press_handler and on_key_release_handler

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
            width=self.ctx.window.width * 0.8,  # type: ignore
            multiline=True,
        )

        self.ctx.current_stimuli = [text]

        self.evloop.add_delayed_callback_once(
            cb=self.end_block, dt=self.ctx.results_show_time_s
        )

    def end_block(self):
        """End the block and log the results"""

        logger.debug("Ending block")

        # Display average reaction time
        # logger.info(f"Reactions {self.ctx.reactions}")   # already show in `show_mean_reaction_time`
        self.ctx.marker_writer.write(self.ctx.endblock_mrk, lsl_marker="end_block")
        self.ctx.close_context()
        self.evloop.stop_event.set()


class StroopClassicTaskStateManager:
    """
    A state manager for the classic Stroop task providing callbacks for state

    Just one state: Word list

    """

    def __init__(self, ctx: StroopContext, random_wait: bool = False):
        self.ctx = ctx  # the context under which to operate

    def transition_to_table(self):
        self.ctx.marker_writer.write(
            self.ctx.startblock_mrk, lsl_marker="start_block_classic"
        )

        self.ctx.current_stimuli = [self.ctx.known_stimuli["classical_batch"]]

        # start the timeout
        pyglet.clock.schedule_once(
            lambda dt: self.end_block(), delay=self.ctx.classical_timeout_s
        )

    def start_block(self):
        """Start a block of trials"""

        logger.debug("Showing intructions")
        self.ctx.marker_writer.write(self.ctx.startblock_mrk, lsl_marker="start_block")

        # Add handler to skip on space press
        self.ctx.window.push_handlers(
            on_key_press=partial(
                instruction_skip_handler_classic,
                ctx=self.ctx,
                smgr=self,
            )
        )

        self.ctx.current_stimuli = [
            self.ctx.known_stimuli["instruction_batch_classical"]
        ]

    def end_block(self):

        self.ctx.marker_writer.write(self.ctx.endblock_mrk, lsl_marker="end_block")
        # show a fixation for 2s so that the stop is not too abrupt
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]

        pyglet.clock.schedule_once(lambda dt: self.close(), delay=2)

    def close(self):
        self.ctx.close_context()
        pass


# ----------------------------------------------------------------------------
#                      Handlers
# ----------------------------------------------------------------------------
def on_escape_exit_handler(symbol, modifiers, ctx: StroopContext):
    """Handle key presses and pop the latest handlers on response"""

    match symbol:
        case pyglet.window.key.ESCAPE:
            logger.debug("Escape key pressed")
            ctx.close_context()


def on_draw(ctx: StroopContext, fps_display: pyglet.window.FPSDisplay | None = None):
    ctx.window.clear()
    # logger.debug("cleared drawing")
    for stim in ctx.current_stimuli:
        stim.draw()

    if fps_display:
        fps_display.draw()


def on_key_press_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Handle key presses and pop the latest handlers on response"""

    match smgr.current_state:
        case "fixation_until_arrow_down":

            if symbol == pyglet.window.key.DOWN and not smgr.down_pressed:
                # start tracking
                smgr.down_pressed = True
                ctx.tic_down = time.perf_counter()
                logger.info("Arrow down pressed")

                # removing any currently waiting callbacks
                smgr.evloop.delayed_callbacks_once = []

                smgr.evloop.add_delayed_callback_once(
                    cb=smgr.next_state, dt=ctx.arrow_down_press_to_continue_s
                )

                return True

        # only react to left right if the stimulus is presented
        case "stimulus":
            match symbol:
                case pyglet.window.key.RIGHT:
                    # Potential logging and LSL here
                    logger.info("RIGHT pressed")
                    handle_reaction("RIGHT", ctx, smgr)
                    return True
                    # breaking of by skipping scheduled manager evctx
                case pyglet.window.key.LEFT:
                    # Potential logging and LSL here
                    logger.info("LEFT pressed")
                    handle_reaction("LEFT", ctx, smgr)
                    return True


def on_key_release_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Handle key presses and pop the latest handlers on response"""

    match smgr.current_state:
        case "fixation_until_arrow_down":
            match symbol:
                case pyglet.window.key.DOWN:
                    # if this happens reset the timer --> so stop the transition
                    smgr.down_pressed = False
                    smgr.evloop.delayed_callbacks_once = []
                    return True

        # only react to left right if the stimulus is presented
        case "stimulus":
            match symbol:
                case pyglet.window.key.DOWN:
                    smgr.down_pressed = False
                    tnow = time.perf_counter()
                    dt_s = tnow - ctx.tic_down
                    dtstim_s = tnow - ctx.tic
                    logger.info(
                        f"Arrow down released after {dt_s=}, compared to stim onset {dtstim_s=}"
                    )
                    ctx.marker_writer.write(
                        ctx.lift_off_mrk,
                        lsl_marker="reaction onset by down key lift off",
                    )
                    return True


def handle_reaction(key: str, ctx: StroopContext, smgr: StroopTaskStateManager):
    """
    First track the time, then deactivate scheduled callbacks and manually
    trigger the next callback
    """
    rtime_s = time.perf_counter() - ctx.tic
    ctx.reactions.append((key, rtime_s))
    ctx.marker_writer.write(ctx.reaction_mrk, lsl_marker=f"reaction_{key}|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")

    # if rtime_s > 2.1:
    #     breakpoint()

    # Remove the scheduled timeout callback because we trigger the next state directly
    smgr.evloop.delayed_callbacks_once = []
    smgr.next_state()


def instruction_skip_handler(
    symbol, modifiers, ctx: StroopContext, smgr: StroopTaskStateManager
):
    """Skip the instructions and start the block"""
    match symbol:
        case pyglet.window.key.SPACE:
            logger.info("User finished instructions")

            # remove the instruction_skip_handler
            for evh_dict in ctx.window._event_stack:
                evh = evh_dict.get("on_key_press", None)

                if evh:
                    func_name = (
                        evh.func.__name__ if isinstance(evh, partial) else evh.__name__
                    )
                    if func_name == "instruction_skip_handler":
                        ctx.window.remove_handler("on_key_press", evh)

            # attach the regulart key press handlers
            ctx.window.push_handlers(
                on_key_press=partial(
                    on_key_press_handler,
                    ctx=ctx,
                    smgr=smgr,
                ),
                on_key_release=partial(on_key_release_handler, ctx=ctx, smgr=smgr),
            )

            # --> show the fixation
            smgr.transition_map[smgr.current_state]()


def instruction_skip_handler_classic(
    symbol, modifiers, ctx: StroopContext, smgr: StroopClassicTaskStateManager
):
    """Skip the instructions and start the block"""
    match symbol:
        case pyglet.window.key.SPACE:
            logger.info("User finished instructions")
            # never pop last layer
            while len(ctx.window._event_stack) > 1:
                ctx.window.pop_handlers()

            smgr.transition_to_table()
