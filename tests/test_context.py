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
