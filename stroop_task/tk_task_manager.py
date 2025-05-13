import os
import random
import time
import tkinter as tk
from functools import partial

from stroop_task.context_tk import TkStroopContext
from stroop_task.utils.logging import logger


class TkStroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self, ctx: TkStroopContext, random_wait: bool = False):
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
        self.down_pressed_tstart = 0
        self.down_pressed = False

        # stop on ESC
        self.ctx.window.bind("<Escape>", lambda _: self.ctx.window.destroy())

        # for book-keeping
        self.timout_event_id: str = ""
        self.next_state_event_id: str = ""

    def start_block(self):
        """Start a block of trials"""

        # # unpack all stimuli to remove from canvas
        # for k, v in self.ctx.known_stimuli.items():
        #     if isinstance(v, dict):
        #         for _, vv in v.items():
        #             vv.place_forget()
        #     elif isinstance(v, list):
        #         for vv in v:
        #             vv.place_forget()
        #     else:
        #         v.place_forget()  # type: ignore

        logger.debug("Showing intructions")
        self.ctx.marker_writer.write(self.ctx.startblock_mrk, lsl_marker="start_block")
        self.ctx.current_stimuli = self.ctx.known_stimuli["instruction_batch"]
        self.place_current_stimuli()

        def skip_instruction(_):
            self.clear_current_stimuli()
            self.ctx.window.unbind("<space>")
            self.show_fixation_until_arrow_down()

        self.ctx.window.bind("<space>", skip_instruction)

    def place_current_stimuli(self):
        for s in self.ctx.current_stimuli:
            s.place()

    def clear_current_stimuli(self):
        for s in self.ctx.current_stimuli:
            s.place_forget()
        self.ctx.current_stimuli = []

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
        self.ctx.window.after(int(self.ctx.pre_stimulus_time_s * 1000), self.next_state)

    def show_fixation_until_arrow_down(self):
        logger.debug("Showing fixation until down press")
        self.clear_current_stimuli()
        self.ctx.marker_writer.write(self.ctx.starttrial_mrk, lsl_marker="start_trial")
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]
        self.place_current_stimuli()

        self.ctx.window.bind(
            "<Down>",
            partial(
                tk_on_key_press_down,
                ctx=self.ctx,
                smgr=self,
            ),
        )

        self.ctx.window.bind(
            "<KeyRelease-Down>",
            partial(
                tk_on_key_release_down,
                smgr=self,
                ctx=self.ctx,
            ),
        )
        # the Release part is set in the tk_on_key_press_down

    def show_stimulus(self):
        """Show the next stimulus in the self.ctx.block_stimuli list"""

        logger.debug("Showing stimulus")
        self.clear_current_stimuli()

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

            self.ctx.window.unbind("<KeyRelease-Down>")
            self.ctx.window.unbind("<Down>")

            self.ctx.window.bind(
                "<KeyRelease-Down>",
                partial(tk_on_key_release_log_onset, ctx=self.ctx, smgr=self),
            )

            self.ctx.window.bind(
                "<Left>",
                partial(tk_on_key_press_left_handler, ctx=self.ctx, smgr=self),
            )
            self.ctx.window.bind(
                "<Right>",
                partial(tk_on_key_press_right_handler, ctx=self.ctx, smgr=self),
            )

            mrk = (
                self.ctx.congruent_mrk
                if cw_top in [e for e, _ in self.ctx.word_color_dict.items()]
                else self.ctx.incongruent_mrk
            )

            # Start showing stimuli (top only)
            self.ctx.current_stimuli = [stim_top]
            self.place_current_stimuli()
            # add bottom after 100ms
            #
            self.ctx.window.after(100, self.show_top_and_bottom_stimulus)

            self.ctx.marker_writer.write(mrk, lsl_marker=f"{cw_top}|{stim_top}")

            # start taking time
            self.ctx.tic = time.perf_counter()

            # Set scheduled timeout << if it reaches here, we timed out
            self.timout_event_id = self.ctx.window.after(
                int(self.ctx.stimulus_time_s * 1000), self.register_timeout
            )

    def show_top_and_bottom_stimulus(self):
        self.clear_current_stimuli()
        cw_top, stim_top, cw_bot, stim_bot = self.ctx.block_stimuli[
            self.ctx.current_stimulus_idx
        ]
        self.ctx.current_stimuli = [stim_top, stim_bot]
        self.ctx.current_stimulus_idx += 1
        self.place_current_stimuli()

    def register_timeout(self):
        rtime_s = time.perf_counter() - self.ctx.tic
        self.ctx.reactions.append(("TIMEOUT", rtime_s))
        self.ctx.marker_writer.write(
            self.ctx.timeout_mrk, lsl_marker=f"timeout|{rtime_s=}"
        )
        logger.info(f"Reaction timeout: {rtime_s=}")
        self.ctx.window.unbind("<Right>")
        self.ctx.window.unbind("<Left>")
        self.ctx.window.unbind("<KeyRelease-Down>")
        self.clear_current_stimuli()
        self.next_state()

    def random_wait(self):
        """
        Using the clock scheduler as sub ms accuracy is not needed anyways
        """

        self.ctx.current_stimuli = []
        self.ctx.window.after(
            int(
                random.uniform(self.ctx.wait_time_min_s, self.ctx.wait_time_max_s)
                * 1000
            ),
            self.next_state,
        )

    def show_mean_reaction_time(self):

        self.clear_current_stimuli()
        logger.info(f"Reaction_times={self.ctx.reactions}")
        mean_reaction_time = sum([e[1] for e in self.ctx.reactions]) / len(
            self.ctx.reactions
        )
        text = tk.Label(
            # text="Please perform the stroop task `<` for incongruent, `>` for"
            # " congruent",
            text=self.ctx.msgs["mean_reaction_time"] + f" {mean_reaction_time:.2f}s",
            fg="#fff",
            font=("Helvetica", self.ctx.font_size),
            width=int(0.8 * self.ctx.window.winfo_screenwidth()),
            wraplength=int(0.8 * self.ctx.window.winfo_screenwidth()),  # type: ignore
        )
        text.place(relx=0.5, rely=0.5, anchor="center")

        self.ctx.current_stimuli = [text]

        self.ctx.window.after(int(self.ctx.results_show_time_s * 1000), self.end_block)

    def end_block(self):
        """End the block and log the results"""
        self.clear_current_stimuli()

        logger.debug("Ending block")

        # Display average reaction time
        logger.info(f"Reactions {self.ctx.reactions}")
        self.ctx.marker_writer.write(self.ctx.endblock_mrk, lsl_marker="end_block")
        self.ctx.close_context()


# ----------------------------------------------------------------------------
#                      Handlers
# ----------------------------------------------------------------------------


def tk_on_key_press_left_handler(
    event, ctx: TkStroopContext, smgr: TkStroopTaskStateManager
):
    logger.info("LEFT pressed")

    rtime_s = time.perf_counter() - ctx.tic
    ctx.reactions.append(("LEFT", rtime_s))
    ctx.marker_writer.write(ctx.reaction_mrk, lsl_marker=f"reaction_LEFT|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")

    ctx.window.after_cancel(smgr.timout_event_id)

    smgr.next_state()


def tk_on_key_press_right_handler(
    event, ctx: TkStroopContext, smgr: TkStroopTaskStateManager
):
    logger.info("RIGHT pressed")

    rtime_s = time.perf_counter() - ctx.tic
    ctx.reactions.append(("RIGHT", rtime_s))
    ctx.marker_writer.write(ctx.reaction_mrk, lsl_marker=f"reaction_RIGHT|{rtime_s=}")
    logger.info(f"Reaction time: {rtime_s=}")

    ctx.window.after_cancel(smgr.timout_event_id)

    smgr.next_state()


def tk_on_key_press_down(event, ctx: TkStroopContext, smgr: TkStroopTaskStateManager):
    if not smgr.down_pressed:
        smgr.down_pressed = True
        logger.debug("Down key pressed")
        try:
            ctx.window.after_cancel(smgr.next_state_event_id)
        except ValueError:
            pass

        smgr.next_state_event_id = ctx.window.after(
            int(ctx.arrow_down_press_to_continue_s * 1000), smgr.next_state
        )


def tk_on_key_release_down(event, smgr: TkStroopTaskStateManager, ctx: TkStroopContext):
    # if this happens reset the timer --> so stop the transition
    if smgr.down_pressed:
        smgr.down_pressed = False
        logger.debug("Down key released")
        smgr.ctx.window.after_cancel(smgr.next_state_event_id)


def tk_on_key_release_log_onset(
    ev, ctx: TkStroopContext, smgr: TkStroopTaskStateManager
):
    smgr.down_pressed = False
    logger.info("Arrow down released")
    ctx.marker_writer.write(
        ctx.lift_off_mrk, lsl_marker="reaction onset by down key lift off"
    )
