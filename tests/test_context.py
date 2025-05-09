import pyglet
import pytest
import yaml

from stroop_task.context import load_context
from stroop_task.utils.logging import logger
from stroop_task.utils.marker import get_marker_writer

logger.setLevel("DEBUG")


def load_context_test(**kwargs):
    # deactivate connection to serial for these tests
    kw = {"write_to_serial": False, "write_to_logger": True, "write_to_lsl": False}
    mw = get_marker_writer(**kw)
    ctx = load_context(marker_writer=mw, **kwargs)
    return ctx


def test_ctx_loading():
    ctx = load_context_test()
    assert ctx.language == "english"  # the default for now


def test_dutch_loading():
    ctx = load_context_test(language="dutch")
    words_cfg = yaml.safe_load(open("./configs/dutch.yaml"))

    for k, v in words_cfg["words"].items():
        assert ctx.word_color_dict[k] == v  # the default for now


def test_ctx_overwrite():
    ctx = load_context_test(
        endblock_mrk=123,
    )

    assert ctx.endblock_mrk == 123


def test_ctx_stimuli_balance():
    kw = {"write_to_serial": False, "write_to_logger": True, "write_to_lsl": False}
    mw = get_marker_writer(**kw)

    ctx = load_context(marker_writer=mw)
    ctx.add_window(pyglet.window.Window(fullscreen=False, height=800, width=1200))

    ctx.create_stimuli()

    assert ctx.block_stimuli == []

    # needs to be multiple of 12 for proper balancing!
    with pytest.raises(ValueError):
        ctx.init_block_stimuli(n_trials=13)

    ctx.init_block_stimuli(n_trials=6)

    coh = [
        tpl for tpl in ctx.block_stimuli if tpl[0].split("_")[0] == tpl[0].split("_")[1]
    ]
    icoh = [
        tpl
        for tpl in ctx.block_stimuli
        if tpl[0].split("_")[0] != tpl[0].split("_")[1] and "XXXX" not in tpl[0]
    ]
    neut = [tpl for tpl in ctx.block_stimuli if "XXXX" in tpl[0]]

    assert len(coh) == len(icoh) == len(neut)

    coh_correct = [tpl for tpl in coh if tpl[0].split("_")[1] == tpl[2]]
    icoh_correct = [tpl for tpl in icoh if tpl[0].split("_")[1] == tpl[2]]
    neut_correct = [tpl for tpl in neut if tpl[0].split("_")[1] == tpl[2]]

    coh_incorrect = [tpl for tpl in coh if tpl[0].split("_")[1] != tpl[2]]
    icoh_incorrect = [tpl for tpl in icoh if tpl[0].split("_")[1] != tpl[2]]
    neut_incorrect = [tpl for tpl in neut if tpl[0].split("_")[1] != tpl[2]]

    assert len(coh_correct) == len(coh_incorrect)
    assert len(icoh_correct) == len(icoh_incorrect)
    assert len(neut_correct) == len(neut_incorrect)
