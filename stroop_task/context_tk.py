import tkinter as tk
from dataclasses import dataclass

import yaml

from stroop_task.context import StroopContext
from stroop_task.utils.logging import logger
from stroop_task.utils.marker import get_marker_writer


def rgba_string_to_hex(rgba_string: str) -> str:
    """Convert a  - ignoring alpha"""
    rgba = rgba_string.replace("(", "").replace(")", "").split(",")
    r = int(rgba[0])
    g = int(rgba[1])
    b = int(rgba[2])
    return f"#{r:02x}{g:02x}{b:02x}"


# to remember the location for pack and unpack...
class MyLabel:
    def __init__(self, *args, **kwargs):
        self.tk_label = tk.Label(*args, **kwargs)
        self.location_params: dict | None = {}
        self.text = kwargs.get("text", "")

    def set_place(self, **kwargs):
        self.location_params = kwargs

    def place(self, **kwargs):
        logger.debug(f"Placing {self.text} with {self.location_params}")
        self.tk_label.place(self.location_params)

    def place_forget(self):
        self.tk_label.place_forget()

    def cget(self, key):
        return self.tk_label.cget(key)


@dataclass
class TkStroopContext(StroopContext):
    """Stroop context for Tkinter"""

    def add_window(self, window: tk.Tk):  # type: ignore
        self.window = window

    def close_context(self):
        """Close the context stopping all pyglet elements"""
        if self.window is not None:
            self.window.destroy()

    def create_stimuli(self, random_wait: bool = True):
        stimuli = {
            "fixation": MyLabel(
                self.window,
                text="+",
                font=("Helvetica", 56),
                fg="gray",
            ),
            "coherent": {
                cw: MyLabel(
                    self.window,
                    text="+",
                    font=("Helvetica", self.font_size),
                    fg=rgba_string_to_hex(cc),
                )
                # .place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                for cw, cc in self.word_color_dict.items()
            },
            "neutral": {
                cw: MyLabel(
                    self.window,
                    text="XXXX",
                    font=("Helvetica", self.font_size),
                    fg=rgba_string_to_hex(cc),
                )
                for cw, cc in self.word_color_dict.items()
            },
            "white": {
                cw: MyLabel(
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
        stimuli["fixation"].set_place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        for k in ["coherent", "neutral", "white"]:
            for v in stimuli[k].values():
                v.set_place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # permute the colors for the incorherent stimuli
        for cw, _ in self.word_color_dict.items():
            for cw2, cc2 in self.word_color_dict.items():
                if cw2 != cw:
                    stimuli["incoherent"][f"{cw}_{cw2}"] = MyLabel(
                        self.window,
                        text=cw,
                        font=("Helvetica", self.font_size),
                        fg=rgba_string_to_hex(cc2),
                    )
                    stimuli["incoherent"][f"{cw}_{cw2}"].set_place(
                        relx=0.5, rely=0.5, anchor=tk.CENTER
                    )

        self.known_stimuli = stimuli
        self.add_instruction_screen_batch()

    def add_instruction_screen_batch(self, random_wait: bool = False):
        """Load all components and add them to an intro batch"""

        instruction_batch = []

        # -> we also need to store each stimulus separately
        self.known_stimuli["instruction_header"] = MyLabel(
            self.window,
            text=self.msgs["instruction_headline"],
            font=("Helvetica", self.instruction_font_size),
            fg="#fff",
            wraplength=int(self.window.winfo_width() * 0.9),
        )
        self.known_stimuli["instruction_header"].set_place(
            relx=0.5, rely=9 / 10, anchor=tk.CENTER
        )

        self.known_stimuli["instruction_footer"] = MyLabel(
            self.window,
            text=self.msgs["instruction_footer"],
            font=("Helvetica", self.instruction_font_size),
            fg="#fff",
            wraplength=int(self.window.winfo_width() * 0.9),
        )
        self.known_stimuli["instruction_footer"].set_place(
            relx=0.5, rely=1 / 12, anchor=tk.CENTER
        )

        instruction_batch.append(self.known_stimuli["instruction_header"])
        instruction_batch.append(self.known_stimuli["instruction_footer"])

        if random_wait:
            congruent_image_x = 4 / 6
            incongruent_image_x = 1 / 6

            self.known_stimuli["instruction_incongruent"] = MyLabel(
                self.window,
                text=self.msgs["incongruent_reaction_color_focus"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=int(self.window.winfo_width() * 0.25),
            )
            self.known_stimuli["instruction_incongruent"].set_place(
                relx=incongruent_image_x, rely=3 / 4, anchor="nw"
            )

            self.known_stimuli["instruction_congruent"] = MyLabel(
                self.window,
                text=self.msgs["incongruent_reaction_color_focus"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=int(self.window.winfo_width() * 0.25),
            )

            self.known_stimuli["instruction_congruent"].set_place(
                relx=congruent_image_x, rely=3 / 4, anchor="nw"
            )

            instruction_batch.append(self.known_stimuli["instruction_congruent"])
            instruction_batch.append(self.known_stimuli["instruction_incongruent"])

        else:
            incongruent_image_x = 3 / 7
            congruent_image_x = 5 / 7

            self.known_stimuli["instruction_incongruent"] = MyLabel(
                self.window,
                text=(
                    self.msgs["incongruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["incongruent_reaction_text_focus"]
                ),
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=int(self.window.winfo_width() * 0.2),
            )
            self.known_stimuli["instruction_incongruent"].set_place(
                relx=incongruent_image_x, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["instruction_congruent"] = MyLabel(
                self.window,
                text=(
                    self.msgs["congruent_reaction_color_focus"]
                    if self.focus == "color"
                    else self.msgs["congruent_reaction_text_focus"]
                ),
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=int(self.window.winfo_width() * 0.2),
            )
            self.known_stimuli["instruction_congruent"].set_place(
                relx=congruent_image_x, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["press_down_instruction"] = MyLabel(
                self.window,
                text=self.msgs["press_down_instruction"],
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
                wraplength=int(self.window.winfo_width() * 0.2),
            )
            self.known_stimuli["press_down_instruction"].set_place(
                relx=1 / 7, rely=4 / 5, anchor="nw"
            )

            self.known_stimuli["instruction_fixation"] = MyLabel(
                self.window,
                text="+",
                font=("Helvetica", self.instruction_font_size),
                fg="#fff",
            )
            self.known_stimuli["instruction_fixation"].set_place(
                relx=3 / 14, rely=9 / 16, anchor="n"
            )

            finger_img = tk.PhotoImage(
                file="./stroop_task/assets/finger_down.png", height=300
            )
            self.known_stimuli["instruction_finger_down_img"] = MyLabel(
                self.window, image=finger_img
            )
            self.known_stimuli["instruction_finger_down_img"].set_place(
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
            self.known_stimuli["instruction_example_congruent_top"] = MyLabel(
                self.window,
                text=self.known_stimuli["coherent"][coh_key].cget("text"),
                fg=self.known_stimuli["coherent"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_top"].set_place(
                relx=congruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_congruent_bot"] = MyLabel(
                self.window,
                text=self.known_stimuli["white"][coh_key].cget("text"),
                fg=self.known_stimuli["white"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_bot"].set_place(
                relx=congruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incogruent_top"] = MyLabel(
                self.window,
                text=self.known_stimuli["incoherent"][incoh_key].cget("text"),
                fg=self.known_stimuli["incoherent"][incoh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incogruent_top"].set_place(
                relx=incongruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incongruent_bot"] = MyLabel(
                self.window,
                text=self.known_stimuli["white"][coh_key].cget("text"),
                fg=self.known_stimuli["white"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incongruent_bot"].set_place(
                relx=incongruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

        if self.focus == "text":
            self.known_stimuli["instruction_example_congruent_top"] = MyLabel(
                self.window,
                text=self.known_stimuli["incoherent"][incoh_key].cget("text"),
                fg=self.known_stimuli["incoherent"][incoh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_top"].set_place(
                relx=congruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_congruent_bot"] = MyLabel(
                self.window,
                text=self.known_stimuli["white"][incoh_key.split("_")[0]].cget("text"),
                fg=self.known_stimuli["white"][incoh_key.split("_")[0]].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_congruent_bot"].set_place(
                relx=congruent_image_x + 1 / 14, rely=8 / 16, anchor=tk.CENTER
            )

            self.known_stimuli["instruction_example_incogruent_top"] = MyLabel(
                self.window,
                text=self.known_stimuli["coherent"][coh_key].cget("text"),
                fg=self.known_stimuli["coherent"][coh_key].cget("fg"),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incogruent_top"].set_place(
                relx=incongruent_image_x + 1 / 14, rely=9 / 16, anchor=tk.CENTER
            )

            # just get a word that does not match
            other_word = [
                w for w in self.known_stimuli["white"].keys() if w != coh_key
            ][0]

            self.known_stimuli["instruction_example_incongruent_bot"] = MyLabel(
                self.window,
                text=self.known_stimuli["white"][other_word].cget("text"),
                fg=rgba_string_to_hex(
                    self.known_stimuli["white"][other_word].cget("fg")
                ),
                font=("Helvetica", int(self.instruction_font_size * 1.2)),
            )
            self.known_stimuli["instruction_example_incongruent_bot"].set_place(
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

        self.known_stimuli["instruction_finger_left_img"] = MyLabel(
            self.window, image=finger_left_img
        )
        self.known_stimuli["instruction_finger_left_img"].set_place(
            relx=incongruent_image_x, rely=1 / 8, anchor="n"
        )

        self.known_stimuli["instruction_finger_right_img"] = MyLabel(
            self.window, image=finger_right_img
        )
        self.known_stimuli["instruction_finger_right_img"].set_place(
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


def load_tk_context(
    language: str = "english", window: tk.Tk | None = None, **kwargs
) -> TkStroopContext:

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
    if window:
        ctx.add_window(window)

    return ctx


if __name__ == "__main__":

    logger.setLevel("DEBUG")
    from stroop_task.utils.marker import get_marker_writer

    mw = get_marker_writer(write_to_serial=False)
    # Needs to be Initialized once here as otherwise the init of the TkStroopContext is breaking
    win = tk.Tk()
    ctx = load_tk_context(marker_writer=mw)
    # ctx = load_tk_context()
    _ = ctx.window.geometry("1200x800")
    ctx.create_stimuli()
