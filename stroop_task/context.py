from dataclasses import dataclass, field, fields

import pyglet
import yaml

from stroop_task.utils.logging import logger
from stroop_task.utils.marker import MarkerWriter, get_marker_writer


@dataclass
class StroopContext:
    # language specific
    language: str
    word_color_dict: dict = field(default_factory=dict)
    msgs: dict = field(default_factory=dict)
    font_size: int = 36

    # markers
    startblock_mrk: int = 64  # 251
    endblock_mrk: int = 64  # 254
    starttrial_mrk: int = 2  # 252
    endtrial_mrk: int = 4  # 253
    congruent_mrk: int = 0  # 1
    incongruent_mrk: int = 0  # 2
    lift_off_mrk: int = 8
    reaction_mrk: int = 16  # 3
    timeout_mrk: int = 16  # 4

    # parametrization
    stimulus_time_s: float = 3.0  # number of seconds to react
    pre_stimulus_time_s: float = 1.0  # time to show the fixation
    wait_time_min_s: float = 1.0  # random wait lower bound
    wait_time_max_s: float = 2.0  # random wait upper bound
    instruction_time_s: float = (
        1000.0  # time to show the instructions, basically show until key press
    )
    results_show_time_s: float = 5.0  # time to show the results

    # paradigm data
    reactions: list = field(default_factory=list)  # tracking
    block_stimuli: list = field(default_factory=list)
    known_stimuli: dict = field(default_factory=dict)
    lsl_outlet: object = None
    current_stimulus_idx: int = 0  # will be used to index block stimuli
    current_stimuli: list = field(default_factory=list)  # tracking stimuli for drawing

    # time keeping
    tic: float = 0
    focus: str = (
        "text"  # can be `text` or `color` (font color), determines which would be considered as correct
    )

    marker_writer: MarkerWriter = field(default_factory=get_marker_writer)

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)
            else:
                logger.debug(f"ignoring kwargs: {k=}, {v=} for StroopContext creation")

    def add_window(self, wd: pyglet.window.BaseWindow):
        self.window = wd


def load_context(language: str = "english", **kwargs) -> StroopContext:
    task_cfg = yaml.safe_load(open("./configs/task.yaml"))
    words_cfg = yaml.safe_load(open(f"./configs/{language}.yaml"))

    kw = {**task_cfg["markers"], **task_cfg["general"], "word_color_dict": words_cfg}

    # use kwargs to overwrite
    kw.update(**kwargs)

    ctx = StroopContext(language=language, **kw)

    return ctx


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    ctx = load_context()
