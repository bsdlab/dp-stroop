# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial

import pyglet
from fire import Fire

from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter

WORD_COLOR_PAIRS = [
    ("red", (255, 0, 0, 255)),
    ("blue", (0, 0, 255, 255)),
    ("green", (0, 255, 0, 255)),
    ("yellow", (255, 255, 0, 255)),
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
    window: pyglet.window.Window = pyglet.window.Window(height=500, width=800)
    reactions: list = field(default_factory=list)  # tracking
    block_stimuli: list = field(default_factory=list)
    known_stimuli: dict = field(default_factory=dict)
    lsl_outlet: object = None
    current_stimulus_idx: int = 0  # will be used to index block stimuli
    current_stimuli: list[pyglet.text.Label] = field(
        default_factory=list
    )  # tracking stimuli for drawing

    # parametrization
    stimulus_time_s: float = 2.0  # number of seconds to react
    pre_stimulus_time_s: float = 1.0  # time to show the fixation
    wait_time_min_s: float = 1.0  # random wait lower bound
    wait_time_max_s: float = 2.0  # random wait upper bound
    instruction_time_s: float = 1.0  # time to show the instructions

    # time keeping
    tic: int = 0

    # marker writer
    marker_writer: MarkerWriter = MarkerWriter("COM4")


CTX = Context()


class StroopTaskStateManager:
    """
    A state manager for the stroop task providing callbacks for state
    transitions from:
    fixation -> stimulus -> random.wait -> fixation ...

    Additionally there is an instructions and end state.
    """

    def __init__(self):
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
        CTX.marker_writer.write(STARTBLOCK_MRK)

        CTX.current_stimuli = [CTX.known_stimuli["instructions"]]

        # transition to show fixation, which will then start the state
        # transitions
        pyglet.clock.schedule_once(
            lambda dt: self.show_fixation(), CTX.instruction_time_s
        )

    def next_state(self, dt=0.0):
        """
        Transition to the next state. dt is only for compliance with pyglet
        callback signature
        """
        curr_i = self.states.index(self.current_state)
        next_i = (curr_i + 1) % len(self.states)
        next_state = self.states[next_i]
        logger.debug(
            f"Transitioning from `{self.current_state}` to " f"`{next_state}`"
        )
        self.current_state = next_state
        self.transition_map[next_state]()

        if next_state == "fixation":
            CTX.marker_writer.write(ENDTRIAL_MRK)

    def show_fixation(self):
        CTX.marker_writer.write(STARTTRIAL_MRK)
        CTX.current_stimuli = [CTX.known_stimuli["fixation"]]
        pyglet.clock.schedule_once(self.next_state, CTX.pre_stimulus_time_s)

    def show_stimulus(self):
        """Show the next stimulus in the CTX.block_stimuli list"""
        CTX.current_stimulus_idx += 1

        logger.debug(f"Showing stimulus {CTX.current_stimulus_idx}")
        # Go to end of block from here
        if CTX.current_stimulus_idx + 1 > len(CTX.block_stimuli):
            self.end_block()
        else:
            stim_name, stim_label = CTX.block_stimuli[CTX.current_stimulus_idx]

            logger.debug(f"Showing stimulus {stim_name=}")

            # Starting to listen to keyboard input
            CTX.window.push_handlers(
                on_key_press=on_key_press_stroop_reaction_handler
            )

            mrk = (
                CONGRUENT_MRK
                if stim_name in WORD_COLOR_PAIRS
                else INCONGRUENT_MRK
            )

            # Start showing stimuli
            CTX.current_stimuli = [stim_label]
            CTX.marker_writer.write(mrk)

            # start taking time
            CTX.tic = time.perf_counter_ns()

            # Set scheduled timeout
            pyglet.clock.schedule_once(
                self.register_timeout, CTX.stimulus_time_s
            )

    def register_timeout(self, dt):
        logger.debug("Registering timeout")
        CTX.reactions.append(("TIMEOUT", time.perf_counter_ns() - CTX.tic))
        CTX.marker_writer.write(TIMEOUT_MRK)
        CTX.window.pop_handlers()
        self.next_state()

    def random_wait(self):
        """
        Using the clock scheduler as sub ms accuracy is not needed anyways
        TODO: Benchmark accurarcy of the clock scheduler
        """
        CTX.current_stimuli = []
        pyglet.clock.schedule_once(
            self.next_state,
            random.uniform(CTX.wait_time_min_s, CTX.wait_time_max_s),
        )

    def end_block(self):
        """End the block and log the results"""

        logger.debug("Ending block")
        logger.info(f"{CTX.reactions}")
        CTX.marker_writer.write(ENDBLOCK_MRK)
        close_context()


SMGR = StroopTaskStateManager()


# ----------------------------------------------------------------------------
#                      Initialization and cleanup
# ----------------------------------------------------------------------------


def close_context():
    """Close the context stopping all pyglet elements"""
    CTX.window.close()


def create_stimuli():
    """Create stimuli for the stroop task using WORD_COLOR_PAIRS"""

    stimuli = {
        "fixation": pyglet.text.Label(
            text="+",
            color=(80, 80, 80, 255),
            font_size=56,
            x=CTX.window.width / 2,
            y=CTX.window.height / 2,
            anchor_x="center",
            anchor_y="center",
        ),
        "instructions": pyglet.text.Label(
            text="Please perform the stroop task `<` for incongruent, `>` for"
            " congruent",
            color=(255, 255, 255, 255),
            font_size=36,
            x=CTX.window.width / 2,
            y=CTX.window.height / 2,
            anchor_x="center",
            anchor_y="center",
            width=CTX.window.width * 0.8,
            multiline=True,
        ),
        "coherent": {
            cw: pyglet.text.Label(
                text=cw,
                color=cc,
                font_size=36,
                x=CTX.window.width / 2,
                y=CTX.window.height / 2,
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
                    x=CTX.window.width / 2,
                    y=CTX.window.height / 2,
                    anchor_x="center",
                    anchor_y="center",
                )

    CTX.known_stimuli = stimuli


def init_block(n_trials: int, incoherent_fraction: float):
    """Initialize a block of trials

    Parameters
    ----------
    n_trials : int
        number of trials per block

    incoherent_fraction : float
        fraction of incoherent trials within n_trials. Will be rounded down
        to next integer value

    """

    # Prepare the stimuli
    n_incoherent = int(incoherent_fraction * n_trials)
    n_coherent = n_trials - n_incoherent
    coherent_stimuli = CTX.known_stimuli["coherent"]
    incoherent_stimuli = CTX.known_stimuli["incoherent"]

    stimuli = [
        (cw, incoherent_stimuli[cw])
        for cw in random.choices(
            list(incoherent_stimuli.keys()), k=n_incoherent
        )
    ] + [
        (cw, coherent_stimuli[cw])
        for cw in random.choices(list(coherent_stimuli.keys()), k=n_coherent)
    ]
    random.shuffle(stimuli)

    CTX.block_stimuli = stimuli


# ----------------------------------------------------------------------------
#                            EVENT HANDLERS
# ----------------------------------------------------------------------------


@CTX.window.event
def on_draw():
    CTX.window.clear()
    for stim in CTX.current_stimuli:
        stim.draw()


def on_key_press_handler(symbol, modifiers):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            close_context()


def on_key_press_stroop_reaction_handler(symbol, modifiers):
    """Handle key presses and pop the latest handlers on response"""
    match symbol:
        case pyglet.window.key.ESCAPE:
            close_context()
        case pyglet.window.key.RIGHT:
            # Potential logging and LSL here
            logger.debug("RIGHT")
            handle_reaction("RIGHT")
            # breaking of by skipping scheduled manager event
        case pyglet.window.key.LEFT:
            # Potential logging and LSL here
            logger.debug("LEFT")
            handle_reaction("LEFT")


def handle_reaction(key: str):
    """
    First track the time, then deactivate scheduled callbacks and manually
    trigger the next callback
    """
    CTX.reactions.append((key, time.perf_counter_ns() - CTX.tic))
    CTX.marker_writer.write(REACTION_MRK)

    CTX.window.pop_handlers()

    # Remove the scheduled callback because me trigger the next state directly
    pyglet.clock.unschedule(SMGR.register_timeout)

    # trigger next state
    SMGR.next_state()


def main():
    logger.setLevel(10)
    create_stimuli()

    # initialize with
    init_block(n_trials=10, incoherent_fraction=0.5)

    pyglet.clock.schedule_once(
        lambda dt: SMGR.start_block(), 0.5
    )  # start after 1 sec
    pyglet.app.run()


if __name__ == "__main__":
    Fire(main)
