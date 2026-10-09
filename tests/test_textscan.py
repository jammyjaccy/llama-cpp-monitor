"""文本扫描：从 commit/release 文本中提取 ADD --xxx 类新增命令。"""
from backend.engine.textscan import scan_new_flags


def test_add_colon_form():
    assert scan_new_flags(["ADD: --new-feature flag support"]) == ["new-feature"]


def test_add_lowercase():
    assert scan_new_flags(["add --foo to llama-server"]) == ["foo"]


def test_added_past_tense():
    assert scan_new_flags(["Added --bar option for testing"]) == ["bar"]


def test_no_match_for_other_verbs():
    assert scan_new_flags(["update --flash-attn behavior", "fix --ctx-size bug"]) == []


def test_multiple_flags_one_message():
    commits = ["ADD: --a and --b flags"]
    assert scan_new_flags(commits) == ["a", "b"]


def test_multiple_messages_dedup_sorted():
    commits = ["ADD: --beta", "add --alpha", "ADD: --beta again"]
    assert scan_new_flags(commits) == ["alpha", "beta"]


def test_flag_with_underscore():
    assert scan_new_flags(["ADD: --my_flag support"]) == ["my_flag"]


def test_empty_input():
    assert scan_new_flags([]) == []
