import json
import random
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from re import split
from typing import Literal

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
    arrow_down_press_to_continue_s: float = 0.5
    classical_timeout_s: float = 45
    focus: Literal["text", "color"] = "color"

    # paradigm data
    reactions: list = field(default_factory=list)  # tracking
    block_stimuli: list = field(default_factory=list)
    known_stimuli: dict = field(default_factory=dict)
    current_stimulus_idx: int = 0  # will be used to index block stimuli
    current_stimuli: list = field(default_factory=list)  # tracking stimuli for drawing

    # GUI
    white_y_offset_px: int = 100
    font_size: int = 36
    instruction_font_size: int = 16
    fullscreen: bool = False
    screen_width: int = 800
    screen_height: int = 600

    # time keeping
    tic: float = 0

    marker_writer: MarkerWriter = field(default_factory=get_marker_writer)
    has_window_attached: bool = False

    def add_window(self, wd: pyglet.window.BaseWindow):
        self.window = wd
        self.has_window_attached = True

    def create_stimuli(self, random_wait: bool = False):
        """Create stimuli for the stroop task using WORD_COLOR_PAIRS"""

        stimuli = {
            "fixation": pyglet.text.Label(
                text="+",
                color=(80, 80, 80, 255),
                font_size=56,
                x=self.window.width // 2,
                y=self.window.height // 2,
                anchor_x="center",
                anchor_y="center",
            ),
            # "instructions": pyglet.text.Label(
            #     # text="Please perform the stroop task `<` for incongruent, `>` for"
            #     # " congruent",
            #     text=self.msgs["instruction"],
            #     color=(255, 255, 255, 255),
            #     font_size=self.font_size,
            #     x=self.window.width // 2,
            #     y=self.window.height // 2,
            #     anchor_x="center",
            #     anchor_y="center",
            #     width=self.window.width * 0.8,
            #     multiline=True,
            # ),
            "coherent": {
                cw: pyglet.text.Label(
                    text=cw,
                    color=eval(cc),  # string to tuple
                    font_size=self.font_size,
                    x=self.window.width // 2,
                    y=self.window.height // 2,
                    anchor_x="center",
                    anchor_y="center",
                )
                for cw, cc in self.word_color_dict.items()
            },
            "neutral": {
                cw: pyglet.text.Label(
                    text="XXXX",
                    color=eval(cc),  # string to tuple
                    font_size=self.font_size,
                    x=self.window.width // 2,
                    y=self.window.height // 2,
                    anchor_x="center",
                    anchor_y="center",
                )
                for cw, cc in self.word_color_dict.items()
            },
            "white": {
                cw: pyglet.text.Label(
                    text=cw,
                    color=(255, 255, 255, 255),
                    font_size=self.font_size,
                    x=self.window.width // 2,
                    y=self.window.height // 2 - self.white_y_offset_px,
                    anchor_x="center",
                    anchor_y="center",
                )
                for cw, _ in self.word_color_dict.items()
            },
            "incoherent": {},
        }

        # permute the colors for the incorherent stimuli
        for cw, _ in self.word_color_dict.items():
            for cw2, cc2 in self.word_color_dict.items():
                if cw2 != cw:
                    stimuli["incoherent"][f"{cw}_{cw2}"] = pyglet.text.Label(
                        text=cw,
                        color=eval(cc2),  # string to tuple
                        font_size=self.font_size,
                        x=self.window.width // 2,
                        y=self.window.height // 2,
                        anchor_x="center",
                        anchor_y="center",
                    )

        self.known_stimuli = stimuli
        self.add_instruction_screen_batch(random_wait=random_wait)

    def add_instruction_screen_batch(self, random_wait: bool = False):
        """Load all components and add them to an intro batch"""

        instruction_batch = pyglet.graphics.Batch()

        # -> we also need to store each stimulus separately
        self.known_stimuli["instruction_header"] = pyglet.text.Label(
            text=self.msgs["instruction_headline"],
            color=(255, 255, 255, 255),
            font_size=self.instruction_font_size,
            x=self.window.width // 2,
            y=int(self.window.height // 10 * 9),
            anchor_x="center",
            anchor_y="center",
            batch=instruction_batch,
            width=int(self.window.width * 0.9),
            multiline=True,
        )

        self.known_stimuli["instruction_footer"] = pyglet.text.Label(
            text=self.msgs["instruction_footer"],
            color=(255, 255, 255, 255),
            font_size=self.instruction_font_size,
            x=self.window.width // 2,
            y=int(self.window.height // 12),
            anchor_x="center",
            anchor_y="center",
            batch=instruction_batch,
        )

        if random_wait:
            # only congruent / incongruent instruction needed

            congruent_image_x = self.window.width // 6 * 4
            incongruent_image_x = self.window.width // 6

            self.known_stimuli["instruction_incongruent"] = pyglet.text.Label(
                text=self.msgs["incongruent_reaction_color_focus"],
                color=(255, 255, 255, 255),
                font_size=self.instruction_font_size,
                x=incongruent_image_x,
                y=self.window.height // 4 * 3,
                anchor_x="left",
                anchor_y="top",
                batch=instruction_batch,
                width=self.window.width // 4,
                multiline=True,
            )

            self.known_stimuli["instruction_congruent"] = pyglet.text.Label(
                text=self.msgs["congruent_reaction_color_focus"],
                color=(255, 255, 255, 255),
                font_size=self.instruction_font_size,
                x=congruent_image_x,
                y=self.window.height // 4 * 3,
                anchor_x="left",
                anchor_y="top",
                batch=instruction_batch,
                width=self.window.width // 4,
                multiline=True,
            )

        else:
            incongruent_image_x = int((self.window.width // 7) * 3)
            congruent_image_x = int((self.window.width // 7) * 5)

            self.known_stimuli["instruction_incongruent"] = pyglet.text.Label(
                text=(
                    self.msgs["incongruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["incongruent_reaction_text_focus"]
                ),
                color=(255, 255, 255, 255),
                font_size=self.instruction_font_size,
                x=incongruent_image_x,
                y=self.window.height // 5 * 4,
                anchor_x="left",
                anchor_y="top",
                batch=instruction_batch,
                width=self.window.width // 5,
                multiline=True,
            )

            self.known_stimuli["instruction_congruent"] = pyglet.text.Label(
                text=(
                    self.msgs["congruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["congruent_reaction_text_focus"]
                ),
                color=(255, 255, 255, 255),
                font_size=self.instruction_font_size,
                x=congruent_image_x,
                y=self.window.height // 5 * 4,
                anchor_x="left",
                anchor_y="top",
                batch=instruction_batch,
                width=self.window.width // 5,
                multiline=True,
            )
            self.known_stimuli["press_down_instruction"] = pyglet.text.Label(
                text=self.msgs["press_down_instruction"],
                color=(255, 255, 255, 255),
                font_size=self.instruction_font_size,
                x=self.window.width // 7,
                y=self.window.height // 5 * 4,
                anchor_x="left",
                anchor_y="top",
                batch=instruction_batch,
                width=self.window.width // 5,
                multiline=True,
            )
            self.known_stimuli["instruction_fixation"] = (
                pyglet.text.Label(
                    text="+",
                    color=(80, 80, 80, 255),
                    font_size=int(self.instruction_font_size * 1.5),
                    x=self.window.width // 7 + self.window.width // 14,
                    y=(self.window.height // 16 * 9),
                    anchor_x="center",
                    anchor_y="top",
                    batch=instruction_batch,
                ),
            )

            self.known_stimuli["instruction_finger_down_img"] = pyglet.sprite.Sprite(
                pyglet.image.load("./stroop_task/assets/finger_down.png"),
                x=self.window.width // 7,
                y=self.window.height // 8,
                batch=instruction_batch,
            )

        # examples of congruent and incongruent
        coh_key = list(self.known_stimuli["coherent"].keys())[0]
        incoh_key = list(self.known_stimuli["incoherent"].keys())[0]

        # if text focus - take incongruent but matching word for correct
        if self.focus == "color":
            self.known_stimuli["instruction_example_congruent_top"] = pyglet.text.Label(
                text=self.known_stimuli["coherent"][coh_key].text,
                color=self.known_stimuli["coherent"][coh_key].color,
                font_size=int(self.instruction_font_size * 1.2),
                x=congruent_image_x + self.window.width // 14,
                y=(self.window.height // 16 * 9),
                anchor_x="center",
                anchor_y="center",
                batch=instruction_batch,
            )

            self.known_stimuli["instruction_example_congruent_bot"] = pyglet.text.Label(
                text=self.known_stimuli["white"][coh_key].text,
                color=self.known_stimuli["white"][coh_key].color,
                font_size=int(self.instruction_font_size * 1.2),
                x=congruent_image_x + self.window.width // 14,
                y=(self.window.height // 16 * 8),
                anchor_x="center",
                anchor_y="center",
                batch=instruction_batch,
            )

            self.known_stimuli["instruction_example_incogruent_top"] = (
                pyglet.text.Label(
                    text=self.known_stimuli["incoherent"][incoh_key].text,
                    color=self.known_stimuli["incoherent"][incoh_key].color,
                    font_size=int(self.instruction_font_size * 1.2),
                    x=incongruent_image_x + self.window.width // 14,
                    y=(self.window.height // 16 * 9),
                    anchor_x="center",
                    anchor_y="center",
                    batch=instruction_batch,
                )
            )

            self.known_stimuli["instruction_example_incongruent_bot"] = (
                pyglet.text.Label(
                    text=self.known_stimuli["white"][coh_key].text,
                    color=self.known_stimuli["white"][coh_key].color,
                    font_size=int(self.instruction_font_size * 1.2),
                    x=incongruent_image_x + self.window.width // 14,
                    y=(self.window.height // 16 * 8),
                    anchor_x="center",
                    anchor_y="center",
                    batch=instruction_batch,
                )
            )

        if self.focus == "text":
            self.known_stimuli["instruction_example_congruent_top"] = pyglet.text.Label(
                text=self.known_stimuli["incoherent"][incoh_key].text,
                color=self.known_stimuli["incoherent"][incoh_key].color,
                font_size=int(self.instruction_font_size * 1.2),
                x=congruent_image_x + self.window.width // 14,
                y=(self.window.height // 16 * 9),
                anchor_x="center",
                anchor_y="center",
                batch=instruction_batch,
            )

            self.known_stimuli["instruction_example_congruent_bot"] = pyglet.text.Label(
                text=self.known_stimuli["white"][incoh_key.split("_")[0]].text,
                color=self.known_stimuli["white"][incoh_key.split("_")[0]].color,
                font_size=int(self.instruction_font_size * 1.2),
                x=congruent_image_x + self.window.width // 14,
                y=(self.window.height // 16 * 8),
                anchor_x="center",
                anchor_y="center",
                batch=instruction_batch,
            )

            self.known_stimuli["instruction_example_incogruent_top"] = (
                pyglet.text.Label(
                    text=self.known_stimuli["coherent"][coh_key].text,
                    font_size=int(self.instruction_font_size * 1.2),
                    color=self.known_stimuli["coherent"][coh_key].color,
                    x=incongruent_image_x + self.window.width // 14,
                    y=(self.window.height // 16 * 9),
                    anchor_x="center",
                    anchor_y="center",
                    batch=instruction_batch,
                )
            )

            # just get a word that does not match
            other_word = [
                w for w in self.known_stimuli["white"].keys() if w != coh_key
            ][0]

            self.known_stimuli["instruction_example_incongruent_bot"] = (
                pyglet.text.Label(
                    text=self.known_stimuli["white"][other_word].text,
                    color=self.known_stimuli["white"][other_word].color,
                    font_size=int(self.instruction_font_size * 1.2),
                    x=incongruent_image_x + self.window.width // 14,
                    y=(self.window.height // 16 * 8),
                    anchor_x="center",
                    anchor_y="center",
                    batch=instruction_batch,
                )
            )

        # --- add the example images
        self.known_stimuli["instruction_finger_left_img"] = pyglet.sprite.Sprite(
            pyglet.image.load("./stroop_task/assets/finger_left.png"),
            x=incongruent_image_x,
            y=self.window.height // 8,
            batch=instruction_batch,
        )
        self.known_stimuli["instruction_finger_right_img"] = pyglet.sprite.Sprite(
            pyglet.image.load("./stroop_task/assets/finger_right.png"),
            x=congruent_image_x,
            y=self.window.height // 8,
            batch=instruction_batch,
        )

        # scale the images to 1/6 of the screens width
        for k, v in self.known_stimuli.items():
            if k.endswith("img"):
                sfactor = (1 / 6) * self.window.width / v.width
                v.width = v.width * sfactor
                v.height = v.height * sfactor

        self.known_stimuli["instruction_batch"] = instruction_batch

    def init_block_stimuli(self, n_trials: int):
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

        if n_trials % 6 != 0:
            raise ValueError(
                f"Please select {n_trials=} to be a multiple of 6 to allow for proper"
                " distribution of congruent, incongruent, and neutral stimuli, with correct/incorrect word in the second row"
            )

        coherent_stimuli = self.known_stimuli["coherent"]
        incoherent_stimuli = self.known_stimuli["incoherent"]
        neutral_stimuli = self.known_stimuli["neutral"]
        white_stimuli = self.known_stimuli["white"]

        # create random sample for the top row - note: do not truncate, as otherwise potentially only red_... would be present

        stimuli = []
        n_each = n_trials // 3
        random.seed(
            1
        )  # work with a fixed seed to reproduce and have same stimuli for all
        for stim_dict in [coherent_stimuli, incoherent_stimuli, neutral_stimuli]:

            if stim_dict == coherent_stimuli:
                stim_aux = [
                    (cw + "_" + cw, stim_dict[cw])
                    for cw, _ in stim_dict.items()
                    for _ in range(n_each)
                ]
            elif stim_dict == neutral_stimuli:
                stim_aux = [
                    (("XXXX_" + cw, stim_dict[cw]))
                    for cw, _ in stim_dict.items()
                    for _ in range(n_each)
                ]

            else:  # incoherent
                stim_aux = [
                    (cw, stim_dict[cw])
                    for cw, _ in stim_dict.items()
                    for _ in range(n_each)
                ]

            pick_idx = random.sample(range(len(stim_aux)), n_each)
            top_stims = [stim_aux[i] for i in pick_idx]

            match_vect = [0, 1] * (n_each // 2)
            random.shuffle(match_vect)

            tstim = []
            for (cw_top, stim_top), match in zip(top_stims, match_vect):
                cwt = cw_top.split("_")[1]

                if match == 1:
                    cw_bot = cwt

                else:
                    cw_bot = random.choice(
                        [cw for cw in white_stimuli.keys() if cw != cwt]
                    )

                stimuli.append((cw_top, stim_top, cw_bot, white_stimuli[cw_bot]))

        random.shuffle(stimuli)

        logger.debug(f"block stimuli: {stimuli}")
        self.block_stimuli = stimuli

    def create_classical_table_stimulus(
        self, n_stimuli: int = 60, n_per_row: int = 6, perc_incongruent: float = 0.33
    ):
        file = Path(
            f"./stroop_task/assets/classical_list_nstim-{n_stimuli}_perc_incongruent-{perc_incongruent:.2f}_lang-{self.language}.json"
        )

        coherent_stimuli = self.known_stimuli["coherent"]
        incoherent_stimuli = self.known_stimuli["incoherent"]
        all_stims = {**coherent_stimuli, **incoherent_stimuli}

        if file.exists():
            logger.debug(f"Loading stimuli from {file}")
            stimuli = json.load(open(file, "r"))["sequence"]
        else:
            logger.debug(f"Creating classical stimuli file at: {file} - random.seed(3)")
            random.seed(3)

            # fix seed to keep creation stable
            n_incoherent = int(n_stimuli * perc_incongruent)
            n_coherent = n_stimuli - n_incoherent

            stimuli = random.choices(
                list(coherent_stimuli.keys()), k=n_coherent
            ) + random.choices(list(incoherent_stimuli.keys()), k=n_incoherent)

            random.shuffle(stimuli)

            json.dump({"sequence": stimuli}, open(file, "w"))

        # sort into rows
        stimuli_arranged = [
            stimuli[i : i + n_per_row] for i in range(0, len(stimuli), n_per_row)
        ]

        # batch stimuli together
        cell_width = self.window.width / n_per_row
        cell_height = self.window.height / len(stimuli_arranged)

        batch = pyglet.graphics.Batch()
        labels = []
        for irow, row in enumerate(stimuli_arranged):
            for icol, stim in enumerate(row):
                template_stim = all_stims[stim]

                # create a new one as stimuli contain c-pointers, which we cannot use deepcopy for
                text_label = pyglet.text.Label(
                    text=template_stim.text,
                    color=template_stim.color,
                    font_size=template_stim.font_size,
                    x=(icol + 1 / 2) * cell_width,  # +1/2 to provide center
                    y=self.window.height - (irow + 1 / 2) * cell_height,
                    anchor_x="center",
                    anchor_y="center",
                    batch=batch,
                )

                # sort top left to bottom right
                labels.append(text_label)

        self.known_stimuli["classical_batch"] = batch
        self.known_stimuli["classical_labels"] = (
            labels  # also store the label list so that it does not get deleted
        )

    def add_instruction_screen_batch_classical(self):

        instruction_batch_classical = pyglet.graphics.Batch()
        self.known_stimuli["instruction_header_classical"] = pyglet.text.Label(
            text=self.msgs["instruction_headline_classical"],
            color=(255, 255, 255, 255),
            font_size=self.instruction_font_size,
            x=self.window.width // 2,
            y=int(self.window.height // 10 * 9),
            anchor_x="center",
            anchor_y="center",
            batch=instruction_batch_classical,
            width=int(self.window.width * 0.9),
            multiline=True,
        )

        self.known_stimuli["instruction_footer"] = pyglet.text.Label(
            text=self.msgs["instruction_footer"],
            color=(255, 255, 255, 255),
            font_size=self.instruction_font_size,
            x=self.window.width // 2,
            y=int(self.window.height // 12),
            anchor_x="center",
            anchor_y="center",
            batch=instruction_batch_classical,
            width=int(self.window.width * 0.9),
            multiline=True,
        )

        self.create_classical_examples_to_batch(instruction_batch_classical)

        self.known_stimuli["instruction_batch_classical"] = instruction_batch_classical

    def create_classical_examples_to_batch(self, batch):
        """Not the full table just a few examples for the instruction screen"""

        coherent_stimuli = self.known_stimuli["coherent"]
        incoherent_stimuli = self.known_stimuli["incoherent"]
        all_stims = {**coherent_stimuli, **incoherent_stimuli}

        random.seed(1)

        # fix seed to keep creation stable
        n_incoherent = 6
        n_coherent = 6

        stimuli = random.choices(
            list(coherent_stimuli.keys()), k=n_coherent
        ) + random.choices(list(incoherent_stimuli.keys()), k=n_incoherent)

        random.shuffle(stimuli)

        n_per_row = 4
        stimuli_arranged = [
            stimuli[i : i + n_per_row] for i in range(0, len(stimuli), n_per_row)
        ]

        # batch stimuli together
        cell_width = self.window.width / (n_per_row + 2)
        cell_height = (self.window.height / 2) / len(
            stimuli_arranged
        )  # only fill half a screen

        labels = []
        for irow, row in enumerate(stimuli_arranged):
            for icol, stim in enumerate(row):
                template_stim = all_stims[stim]

                # create a new one as stimuli contain c-pointers, which we cannot use deepcopy for
                text_label = pyglet.text.Label(
                    text=template_stim.text,
                    color=template_stim.color,
                    font_size=template_stim.font_size,
                    x=(icol + 1 / 2 + 1)
                    * cell_width,  # +1/2 to provide center , +1 cell padding left and right
                    y=(self.window.height * 3 / 4) - (irow + 1 / 2) * cell_height,
                    anchor_x="center",
                    anchor_y="center",
                    batch=batch,
                )

                # sort top left to bottom right
                labels.append(text_label)

        self.known_stimuli["classical_labels_intro"] = (
            labels  # also store the label list so that it does not get deleted
        )

    def init_classical(self):
        self.create_classical_table_stimulus()

        # also create a classical instuction
        self.add_instruction_screen_batch_classical()

    def close_context(self):
        """Close the context stopping all pyglet elements"""
        if self.has_window_attached:
            self.window.close()


def rgba_string_to_hex(rgba_string: str) -> str:
    """Convert a  - ignoring alpha"""
    rgba = rgba_string.replace("(", "").replace(")", "").split(",")
    r = int(rgba[0])
    g = int(rgba[1])
    b = int(rgba[2])
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class TkStroopContext(StroopContext):
    """Stroop context for Tkinter"""

    def __post_init__(self):
        self.window: tk.Tk = tk.Tk()

    def close_context(self):
        """Close the context stopping all pyglet elements"""
        if self.window is not None:
            self.window.destroy()

    def create_stimuli(self, random_wait: bool = True):
        stimuli = {
            "fixation": tk.Label(
                self.window,
                text="+",
                font=("Helvetica", 56),
                fg="gray",
            ),
            "coherent": {
                cw: tk.Label(
                    self.window,
                    text="+",
                    font=("Helvetica", self.font_size),
                    fg=rgba_string_to_hex(cc),
                )
                # .place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                for cw, cc in self.word_color_dict.items()
            },
            "neutral": {
                cw: tk.Label(
                    self.window,
                    text="XXXX",
                    font=("Helvetica", self.font_size),
                    fg=rgba_string_to_hex(cc),
                )
                for cw, cc in self.word_color_dict.items()
            },
            "white": {
                cw: tk.Label(
                    self.window,
                    text="+",
                    font=("Helvetica", self.font_size),
                    fg="white",
                )
                for cw, cc in self.word_color_dict.items()
            },
            "incoherent": {},
        }

        # place all at center
        stimuli["fixation"].place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        for k in ["coherent", "neutral", "white"]:
            for v in stimuli[k].values():
                v.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # permute the colors for the incorherent stimuli
        for cw, _ in self.word_color_dict.items():
            for cw2, cc2 in self.word_color_dict.items():
                if cw2 != cw:
                    stimuli["incoherent"][f"{cw}_{cw2}"] = tk.Label(
                        self.window,
                        text=cw,
                        font=("Helvetica", self.font_size),
                        fg=rgba_string_to_hex(cc2),
                    )
                    stimuli["incoherent"][f"{cw}_{cw2}"].place(
                        relx=0.5, rely=0.5, anchor=tk.CENTER
                    )

        self.known_stimuli = stimuli
        self.add_instruction_screen_batch()

    def add_instruction_screen_batch(self, random_wait: bool = False):
        """Load all components and add them to an intro batch"""

        instruction_batch = []

        # -> we also need to store each stimulus separately
        self.known_stimuli["instruction_header"] = tk.Label(
            self.window,
            text=self.msgs["instruction_headline"],
            font=("Helvetica", self.instruction_font_size),
            fg="#fff",
            wraplength=self.window.winfo_width() * 0.9,
        )
        self.known_stimuli["instruction_header"].place(
            relx=0.5, rely=9 / 10, anchor=tk.CENTER
        )

        self.known_stimuli["instruction_footer"] = tk.Label(
            self.window,
            text=self.msgs["instruction_footer"],
            font=("Helvetica", self.instruction_font_size),
            fg="#fff",
            wraplength=self.window.winfo_width() * 0.9,
        )
        self.known_stimuli["instruction_footer"].place(
            relx=0.5, rely=1 / 12, anchor=tk.CENTER
        )

        instruction_batch.append(self.known_stimuli["instruction_header"])
        instruction_batch.append(self.known_stimuli["instruction_footer"])

        if random_wait:
            congruent_image_x = 4 / 6
            incongruent_image_x = 1 / 6

            self.known_stimuli["instruction_incongruent"] = tk.Label(
                self.window,
                text=self.msgs["incongruent_reaction_color_focus"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=self.window.winfo_width() * 0.25,
            )
            self.known_stimuli["instruction_incongruent"].place(
                x=incongruent_image_x, y=3 / 4, anchor="nw"
            )

            self.known_stimuli["instruction_congruent"] = tk.Label(
                self.window,
                text=self.msgs["incongruent_reaction_color_focus"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=self.window.winfo_width() * 0.25,
            )

            self.known_stimuli["instruction_congruent"].place(
                x=congruent_image_x, y=3 / 4, anchor="nw"
            )

            instruction_batch.append(self.known_stimuli["instruction_congruent"])
            instruction_batch.append(self.known_stimuli["instruction_incongruent"])

        else:
            incongruent_image_x = 3 / 7
            congruent_image_x = 5 / 7

            self.known_stimuli["instruction_incongruent"] = tk.Label(
                self.window,
                text=(
                    self.msgs["incongruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["incongruent_reaction_text_focus"]
                ),
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=self.window.winfo_width() * 0.2,
            )
            self.known_stimuli["instruction_incongruent"].place(
                relx=incongruent_image_x, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["instruction_congruent"] = tk.Label(
                self.window,
                text=(
                    self.msgs["congruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["congruent_reaction_text_focus"]
                ),
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=self.window.winfo_width() * 0.2,
            )
            self.known_stimuli["instruction_congruent"].place(
                relx=congruent_image_x, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["press_down_instruction"] = tk.Label(
                self.window,
                text=self.msgs["press_down_instruction"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=self.window.winfo_width() * 0.2,
            )
            self.known_stimuli["press_down_instruction"].place(
                relx=1 / 7, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["instruction_fixation"] = tk.Label(
                self.window,
                text="+",
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
            )
            self.known_stimuli["instruction_fixation"].place(
                relx=3 / 14, rely=9 / 16, anchor="n"
            )

            finger_img = tk.PhotoImage(
                file="./stroop_task/assets/finger_down.png", height=300
            )
            self.known_stimuli["instruction_finger_down_img"] = tk.Label(
                self.window, image=finger_img
            )
            self.known_stimuli["instruction_finger_down_img"].place(
                relx=1 / 7, rely=1 / 8, anchor="n"
            )

            instruction_batch.append(self.known_stimuli["instruction_congruent"])
            instruction_batch.append(self.known_stimuli["instruction_incongruent"])
            instruction_batch.append(self.known_stimuli["press_down_instruction"])
            instruction_batch.append(self.known_stimuli["instruction_fixation"])

        # examples of congruent and incongruent
        coh_key = list(self.known_stimuli["coherent"].keys())[0]
        incoh_key = list(self.known_stimuli["incoherent"].keys())[0]

        # if text focus - take incongruent but matching word for correct
        if self.focus == "color":
            self.known_stimuli["instruction_example_congruent_top"] = tk.Label(
                self.window,
                text=self.known_stimuli["coherent"][coh_key].cget("text"),
                fg=self.known_stimuli["coherent"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_top"].place(
                relx=congruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_congruent_bot"] = tk.Label(
                self.window,
                text=self.known_stimuli["white"][coh_key].cget("text"),
                fg=self.known_stimuli["white"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_bot"].place(
                relx=congruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incogruent_top"] = tk.Label(
                self.window,
                text=self.known_stimuli["incoherent"][incoh_key].cget("text"),
                fg=self.known_stimuli["incoherent"][incoh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incogruent_top"].place(
                relx=incongruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incongruent_bot"] = tk.Label(
                self.window,
                text=self.known_stimuli["white"][coh_key].cget("text"),
                fg=self.known_stimuli["white"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incongruent_bot"].place(
                relx=incongruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

        if self.focus == "text":
            self.known_stimuli["instruction_example_congruent_top"] = tk.Label(
                self.window,
                text=self.known_stimuli["incoherent"][incoh_key].cget("text"),
                fg=self.known_stimuli["incoherent"][incoh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_top"].place(
                relx=congruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_congruent_bot"] = tk.Label(
                self.window,
                text=self.known_stimuli["white"][incoh_key.split("_")[0]].cget("text"),
                fg=self.known_stimuli["white"][incoh_key.split("_")[0]].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_bot"].place(
                relx=congruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incogruent_top"] = tk.Label(
                self.window,
                text=self.known_stimuli["coherent"][coh_key].cget("text"),
                fg=self.known_stimuli["coherent"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incogruent_top"].place(
                relx=incongruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            # just get a word that does not match
            other_word = [
                w for w in self.known_stimuli["white"].keys() if w != coh_key
            ][0]

            self.known_stimuli["instruction_example_incongruent_bot"] = tk.Label(
                self.window,
                text=self.known_stimuli["white"][other_word].cget("text"),
                fg=rgba_string_to_hex(
                    self.known_stimuli["white"][other_word].cget("fg")
                ),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incongruent_bot"].place(
                relx=incongruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

        instruction_batch.append(
            self.known_stimuli["instruction_example_congruent_top"]
        )
        instruction_batch.append(
            self.known_stimuli["instruction_example_congruent_bot"]
        )
        instruction_batch.append(
            self.known_stimuli["instruction_example_incogruent_top"]
        )
        instruction_batch.append(
            self.known_stimuli["instruction_example_incongruent_bot"]
        )

        # --- add the example images
        finger_left_img = tk.PhotoImage(
            file="./stroop_task/assets/finger_left.png", height=300
        )
        finger_right_img = tk.PhotoImage(
            file="./stroop_task/assets/finger_right.png", height=300
        )

        self.known_stimuli["instruction_finger_left_img"] = tk.Label(
            self.window, image=finger_left_img
        )
        self.known_stimuli["instruction_finger_left_img"].place(
            relx=incongruent_image_x, rely=1 / 8, anchor="n"
        )

        self.known_stimuli["instruction_finger_right_img"] = tk.Label(
            self.window, image=finger_right_img
        )
        self.known_stimuli["instruction_finger_right_img"].place(
            relx=congruent_image_x, rely=1 / 8, anchor="n"
        )

        # # scale the images to 1/6 of the screens width
        # for k, v in self.known_stimuli.items():
        #     if k.endswith("img"):
        #         sfactor = (1 / 6) * self.window.width / v.width
        #         v.width = v.width * sfactor
        #         v.height = v.height * sfactor

        instruction_batch.append(self.known_stimuli["instruction_finger_left_img"])
        instruction_batch.append(self.known_stimuli["instruction_finger_right_img"])

        self.known_stimuli["instruction_batch"] = instruction_batch


def load_context(language: str = "english", **kwargs) -> StroopContext:
    task_cfg = yaml.safe_load(open("./configs/task.yaml"))
    language_cfg = yaml.safe_load(open(f"./configs/{language}.yaml"))
    gui_cfg = yaml.safe_load(open("./configs/gui.yaml"))

    kw = {
        **task_cfg["markers"],
        **task_cfg["general"],
        **gui_cfg,
        "word_color_dict": language_cfg["words"],
        "msgs": language_cfg["msgs"],
    }

    # use kwargs to overwrite
    kw.update(**kwargs)

    # log the parameters to the data as well
    logger.info(f"Creating StroopContext with {kw=}")

    ctx = StroopContext(language=language, **kw)

    return ctx


def load_tk_context(language: str = "english", **kwargs) -> TkStroopContext:

    task_cfg = yaml.safe_load(open("./configs/task.yaml"))
    language_cfg = yaml.safe_load(open(f"./configs/{language}.yaml"))
    gui_cfg = yaml.safe_load(open("./configs/gui.yaml"))

    kw = {
        **task_cfg["markers"],
        **task_cfg["general"],
        **gui_cfg,
        "word_color_dict": language_cfg["words"],
        "msgs": language_cfg["msgs"],
    }

    # use kwargs to overwrite
    kw.update(**kwargs)

    # log the parameters to the data as well
    logger.info(f"Creating TkStroopContext with {kw=}")

    ctx = TkStroopContext(language=language, **kw)

    return ctx


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    from stroop_task.utils.marker import get_marker_writer

    mw = get_marker_writer(write_to_serial=False)

    ctx = load_context(marker_writer=mw)
    ctx.add_window(pyglet.window.Window(fullscreen=False, height=800, width=1200))
    ctx.create_stimuli()

    # in the tkinter version, we just overwrite
    ctx = load_tk_context(marker_writer=mw)
    _ = ctx.window.geometry("1200x800")
    ctx.create_stimuli()
    ctx.init_classical()
