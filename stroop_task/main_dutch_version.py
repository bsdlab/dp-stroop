# A pyglet implementation of the stroop task

import random
import time
from dataclasses import dataclass, field
from functools import partial
from subprocess import Popen
import serial

import pyglet
from fire import Fire

from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter

#from utils.logging import logger
#from utils.marker import MarkerWriter

WORD_COLOR_PAIRS = [
    #("red", (255, 0, 0, 255)),
    #("blue", (0, 0, 255, 255)),
    #("green", (0, 255, 0, 255)),
    #("yellow", (255, 255, 0, 255)),
    ("rood", (255, 0, 0, 255)),
    ("blauw", (0, 0, 255, 255)),
    ("groen", (0, 255, 0, 255)),
    ("geel", (255, 255, 0, 255)),
]
isSer=0
if isSer:
    Ser.port = 'COM9' # replace COMx with the actual COM port name
    Ser.open()
STARTBLOCK_MRK = 251
ENDBLOCK_MRK = 254
STARTTRIAL_MRK = 252
ENDTRIAL_MRK = 253
CONGRUENT_MRK = 1
INCONGRUENT_MRK = 2
REACTION_MRK = 3
TIMEOUT_MRK = 4
trigger_startblock_mrk=2
trigger_endblock_mrk=2
trigger_endtrial_mrk=4
trigger_starttrial_mrk=4
trigger_congruent_mrk=16
#trigger_incongruentmrk=
trigger_reaction_mrk=64
trigger_timeout_mrk=64


# A data structure for easier access
@dataclass
class Context:
    window: pyglet.window.Window = pyglet.window.Window(height=500, width=800)
    window.set_fullscreen(True)
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
    instruction_time_s: float = 10.0  # time to show the instructions

    # time keeping
    tic: int = 0
    marker_writer: MarkerWriter | None = None

    # marker writer
    def __post_init__(self):
        self.marker_writer: MarkerWriter = MarkerWriter("COM4")


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
        Trigger=trigger_startblock_mrk
        self.ctx.marker_writer.write(STARTBLOCK_MRK)
        if isSer:
            Ser.write(bytes(chr(Trigger),encoding='utf8'))
        self.ctx.current_stimuli = [self.ctx.known_stimuli["instructions"]]

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
        logger.debug(
            f"Transitioning from `{self.current_state}` to " f"`{next_state}`"
        )
        self.current_state = next_state
        self.transition_map[next_state]()
        Trigger=trigger_endtrial_mrk
        if next_state == "fixation":
            self.ctx.marker_writer.write(ENDTRIAL_MRK)
            if isSer:
                Ser.write(bytes(chr(Trigger),encoding='utf8'))

    def show_fixation(self):
        Trigger=trigger_starttrial_mrk
        self.ctx.marker_writer.write(STARTTRIAL_MRK)
        if isSer:
            Ser.write(bytes(chr(Trigger),encoding='utf8'))
        self.ctx.current_stimuli = [self.ctx.known_stimuli["fixation"]]
        pyglet.clock.schedule_once(
            self.next_state, self.ctx.pre_stimulus_time_s
        )

    def show_stimulus(self):
        """Show the next stimulus in the self.ctx.block_stimuli list"""
        self.ctx.current_stimulus_idx += 1

        logger.debug(f"Showing stimulus {self.ctx.current_stimulus_idx}")
        # Go to end of block from here
        if self.ctx.current_stimulus_idx + 1 > len(self.ctx.block_stimuli):
            self.end_block()
        else:
            stim_name, stim_label = self.ctx.block_stimuli[
                self.ctx.current_stimulus_idx
            ]

            logger.debug(f"Showing stimulus {stim_name=}")

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
            Trigger=trigger_congruent_mrk

            # Start showing stimuli
            self.ctx.current_stimuli = [stim_label]
            self.ctx.marker_writer.write(mrk)
            if isSer:
                Ser.write(bytes(chr(Trigger),encoding='utf8'))

            # start taking time
            self.ctx.tic = time.perf_counter_ns()

            # Set scheduled timeout
            pyglet.clock.schedule_once(
                self.register_timeout, self.ctx.stimulus_time_s
            )

    def register_timeout(self, dt):
        logger.debug("Registering timeout")
        self.ctx.reactions.append(
            ("TIMEOUT", time.perf_counter_ns() - self.ctx.tic)
        )
        Trigger=trigger_timeout_mrk
        self.ctx.marker_writer.write(TIMEOUT_MRK)
        if isSer:
            Ser.write(bytes(chr(Trigger),encoding='utf8'))
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

    def end_block(self):
        """End the block and log the results"""

        logger.debug("Ending block")
        logger.info(f"{self.ctx.reactions}")
        Trigger=trigger_endblock_mrk
        self.ctx.marker_writer.write(ENDBLOCK_MRK)
        close_context(self.ctx)


# ----------------------------------------------------------------------------
#                      Initialization and cleanup
# ----------------------------------------------------------------------------


def close_context(ctx: Context):
    """Close the context stopping all pyglet elements"""
    if isSer:
        Ser.close()
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
            #text="Please perform the stroop task `<` for incongruent, `>` for"
            #" congruent",
            text="Bedankt voor uw deelname aan deze taak. Kijk naar de gekleurde woorden.""\n"
            " Als woordbetekenis en kleur NIET overeenkomen druk dan op `<`.""\n"
            " Als woordbetekenis en kleur overeenkomen druk dan op `>` .",
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

    ctx.known_stimuli = stimuli


def init_block_stimuli(
    n_trials: int, incoherent_fraction: float, ctx: Context
):
    """Initialize a block of trials by modifying a context

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
    coherent_stimuli = ctx.known_stimuli["coherent"]
    incoherent_stimuli = ctx.known_stimuli["incoherent"]

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
    ctx.reactions.append((key, time.perf_counter_ns() - ctx.tic))
    Trigger=trigger_reaction_mrk
    ctx.marker_writer.write(REACTION_MRK)
    if isSer:
            Ser.write(bytes(chr(Trigger),encoding='utf8'))
    ctx.window.pop_handlers()
    # Remove the scheduled callback because me trigger the next state directly
    pyglet.clock.unschedule(smgr.register_timeout)

    # trigger next state
    smgr.next_state()


def main(
    n_trials: int = 60,
    incoherent_fraction: float = 0.5,
    logger_level: int = 30,
):
    if logger_level:
        logger.setLevel(logger_level)

    ctx = Context()

    smgr = StroopTaskStateManager(ctx=ctx)

    # Hook up the drawing callback
    pon_draw = partial(on_draw, ctx=ctx)
    ctx.window.push_handlers(on_draw=pon_draw)

    # Init
    create_stimuli(ctx)
    init_block_stimuli(n_trials, incoherent_fraction, ctx)
    # Start running
    pyglet.clock.schedule_once(
        lambda dt: smgr.start_block(), 0.5
    )  # start after 1 sec
    try:
        pyglet.app.run()
    finally:
        close_context(ctx)


def run_block_subprocess(**kwargs):
    kwargs_str = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
    cmd = "python -m stroop_task.main " + kwargs_str
    pid = Popen(cmd, shell=True)
    return pid


if __name__ == "__main__":
    Fire(main)
