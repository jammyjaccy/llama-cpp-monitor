"""help-diff：两份 --help 文本 diff 出新增 flag。"""
from backend.engine.helpdiff import diff_help_texts

OLD_HELP = """llama-server:
  --help            Show this help
  --model PATH      Model path
  --ctx-size N      Context size
  --flash-attn      Flash attention
"""

NEW_HELP = """llama-server:
  --help            Show this help
  --model PATH      Model path
  --ctx-size N      Context size [default: 4096]
  --flash-attn      Flash attention
  --new-flag        A brand new flag
  --spec-draft-n-max N  New MTP flag
"""


def test_finds_new_flags():
    result = diff_help_texts(OLD_HELP, NEW_HELP)
    flags = {f["flag"] for f in result}
    assert flags == {"new-flag", "spec-draft-n-max"}


def test_no_new_flags():
    assert diff_help_texts(OLD_HELP, OLD_HELP) == []


def test_removed_flag_not_reported():
    old = "  --old-flag  something\n  --keep\n"
    new = "  --keep\n"
    result = diff_help_texts(old, new)
    assert [f["flag"] for f in result] == []


def test_description_captured():
    result = diff_help_texts("  --a\n", "  --a\n  --new-flag        Does the thing\n")
    assert result[0]["flag"] == "new-flag"
    assert "Does the thing" in result[0]["description"]


def test_empty_old_text_treated_as_baseline():
    result = diff_help_texts("", NEW_HELP)
    assert len(result) == 6  # help, model, ctx-size, flash-attn, new-flag, spec-draft-n-max
    # 空基线：所有 flag 都算新增
    assert {f["flag"] for f in result} == {
        "help", "model", "ctx-size", "flash-attn", "new-flag", "spec-draft-n-max",
    }


def test_flag_line_format_variants():
    old = ""
    new = "usage: llama-server [options]\n  --foo-bar  desc here\n    --baz    indented desc\n"
    flags = {f["flag"] for f in diff_help_texts(old, new)}
    assert "foo-bar" in flags
    assert "baz" in flags
