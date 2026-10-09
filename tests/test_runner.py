"""Runner：增量任务编排。

覆盖：新版本处理、文本扫描落库、LLM 分析落库、条件 help-diff、
LLM 失败补分析、GitHub 失败 run=failed、重入拒绝。
"""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend import config
from backend.database import Base
from backend.engine.llm import LLMError
from backend.engine.runner import BusyError, Runner
from backend.models import NewCommand, Version


class FakeFetcher:
    def __init__(self, releases=None, compare_data=None, fail=False):
        self.releases = releases or []
        self.compare_data = compare_data or {}
        self.fail = fail
        self.compare_calls = []

    def list_releases(self, per_page=100):
        if self.fail:
            raise RuntimeError("GitHub unreachable")
        return self.releases

    def compare(self, prev_tag, tag):
        if self.fail:
            raise RuntimeError("GitHub unreachable")
        self.compare_calls.append((prev_tag, tag))
        return self.compare_data.get(tag, {"total_commits": 0, "commits": []})

    def download_url(self, tag, platform="win-cuda-12.4-x64"):
        return f"https://example.com/{tag}.zip"


class FakeLLM:
    def __init__(self, result=None, fail=False):
        self.result = result or {
            "has_positive": False,
            "positive_items": [],
            "launch_impact": {"flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": ""},
            "suggested_flags": [],
        }
        self.fail = fail
        self.calls = []

    def analyze(self, commits, launch_command, tag=""):
        self.calls.append(tag)
        if self.fail:
            raise LLMError("LLM down")
        return self.result


class FakeHelpCache:
    def __init__(self, texts=None):
        self.texts = texts or {}
        self.saved = {}
        self.latest = None
        self._tags = []

    def load_help(self, tag):
        if tag in self.saved:
            return self.saved[tag]
        return self.texts.get(tag, "")

    def save_help(self, tag, text):
        self.saved[tag] = text
        self._tags.append(tag)
        self.latest = tag

    def latest_tag(self):
        return self.latest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    # ADR-0004：模型默认值来自 .env；测试用固定值，不依赖真实 .env
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
    })
    with Session() as s:
        config.load_settings(s)
    return Session


def make_runner(env, fetcher, llm, cache=None):
    return Runner(
        db_factory=env,
        fetcher=fetcher,
        llm=llm,
        help_cache=cache or FakeHelpCache(),
    )


RELEASES = [
    {"tag_name": "b11518", "published_at": "2026-10-09T01:00:00Z", "body": "release b11518"},
    {"tag_name": "b11519", "published_at": "2026-10-09T02:00:00Z", "body": "release b11519"},
]
COMPARE = {
    "b11518": {
        "total_commits": 2,
        "commits": [
            {"sha": "aaa111", "message": "CUDA: improve flash-attn perf"},
            {"sha": "bbb222", "message": "ADD: --new-flag for testing"},
        ],
    },
    "b11519": {
        "total_commits": 1,
        "commits": [{"sha": "ccc333", "message": "docs: update readme"}],
    },
}
POSITIVE_RESULT = {
    "has_positive": True,
    "positive_items": [{"item": "x", "reason": "y"}],
    "launch_impact": {
        "flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": "",
    },
    "suggested_flags": [],
}


def test_processes_new_versions_ascending(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    llm = FakeLLM()
    runner = make_runner(env, fetcher, llm)
    run = runner.run("manual")

    assert run.status == "ok"
    assert json.loads(run.versions_processed) == ["b11518", "b11519"]
    # 升序处理
    assert llm.calls == ["b11518", "b11519"]
    # compare 用 v 的上一版（b{N-1}），基线本身不入库（design §5.1a）
    assert fetcher.compare_calls[0] == ("b11517", "b11518")
    assert fetcher.compare_calls[1] == ("b11518", "b11519")

    with env() as s:
        versions = {v.tag: v for v in s.execute(select(Version)).scalars()}
        assert set(versions) == {"b11518", "b11519"}
        assert versions["b11518"].commit_count == 2
        assert versions["b11518"].analyzed == 1


def test_text_scan_writes_new_commands(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    runner = make_runner(env, fetcher, FakeLLM())
    runner.run("manual")

    with env() as s:
        cmds = list(s.execute(select(NewCommand)).scalars())
        assert len(cmds) == 1
        assert cmds[0].tag == "b11518"
        assert cmds[0].flag == "new-flag"
        assert cmds[0].source == "text"


def test_text_scan_reads_nested_commit_message(env):
    """GitHub compare 的 commit 消息在嵌套层 commit.message，文本扫描须读到。"""
    releases = [{"tag_name": "b11518", "published_at": "2026-10-09T01:00:00Z", "body": ""}]
    compare = {
        "b11518": {
            "total_commits": 1,
            "commits": [
                {"sha": "x", "commit": {"message": "ADD --nested-flag for testing"}},
            ],
        }
    }
    fetcher = FakeFetcher(releases, compare)
    runner = make_runner(env, fetcher, FakeLLM())
    runner.run("manual")

    with env() as s:
        cmds = list(s.execute(select(NewCommand)).scalars())
        assert len(cmds) == 1
        assert cmds[0].flag == "nested-flag"
        assert cmds[0].source == "text"


def test_positive_triggers_help_diff(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    llm = FakeLLM(result={
        "has_positive": True,
        "positive_items": [{"item": "flash-attn perf", "reason": "用户用了 flash-attn"}],
        "launch_impact": {"flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": ""},
        "suggested_flags": [],
    })
    cache = FakeHelpCache(texts={"b11517": "  --help  Show help\n"})
    runner = make_runner(env, fetcher, llm, cache)
    # 模拟下载：monkeypatch download_help
    import backend.engine.runner as runner_mod

    downloaded = []

    def fake_download_help(f, tag, c):
        downloaded.append(tag)
        text = "  --help  Show help\n  --brand-new  New flag\n"
        c.save_help(tag, text)
        return text

    orig = runner_mod.download_help
    runner_mod.download_help = fake_download_help
    try:
        run = runner.run("manual")
    finally:
        runner_mod.download_help = orig

    assert run.status == "ok"
    # b11518 与 b11519 均有正提升；b11519 的上一版 b11518 已缓存
    assert downloaded == ["b11518", "b11519"]
    assert cache.saved.get("b11518") is not None
    with env() as s:
        v = s.execute(select(Version).where(
            Version.tag == "b11518")).scalar_one()
        assert v.help_diffed == 1
        assert json.loads(v.positive_items)[0]["item"] == "flash-attn perf"
        cmds = [c for c in s.execute(select(NewCommand)).scalars()
                if c.tag == "b11518"]
        sources = {c.flag: c.source for c in cmds}
        assert sources.get("brand-new") == "help-diff"
        assert sources.get("new-flag") == "text"


def test_help_diff_establishes_missing_prev_baseline(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    llm = FakeLLM(result=POSITIVE_RESULT)
    cache = FakeHelpCache()  # 无任何缓存
    runner = make_runner(env, fetcher, llm, cache)
    import backend.engine.runner as runner_mod

    downloaded = []

    def fake_download_help(f, tag, c):
        downloaded.append(tag)
        text = f"  --help  Show help\n  --flag-of-{tag}\n"
        c.save_help(tag, text)
        return text

    orig = runner_mod.download_help
    runner_mod.download_help = fake_download_help
    try:
        runner.run("manual")
    finally:
        runner_mod.download_help = orig

    # b11518：先补下载上一版 b11517 建立基线，再下载 b11518；b11519 同理
    assert downloaded == ["b11517", "b11518", "b11519"]
    with env() as s:
        cmds = {c.flag: c.source for c in s.execute(
            select(NewCommand)).scalars() if c.tag == "b11518"}
        assert cmds.get("flag-of-b11518") == "help-diff"


def test_help_diff_failure_marks_not_diffed(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    llm = FakeLLM(result=POSITIVE_RESULT)
    cache = FakeHelpCache(texts={"b11517": "old"})
    runner = make_runner(env, fetcher, llm, cache)
    import backend.engine.runner as runner_mod
    from backend.engine.helpdiff_exec import HelpDiffError

    def boom(f, tag, c):
        raise HelpDiffError("download failed")

    orig = runner_mod.download_help
    runner_mod.download_help = boom
    try:
        run = runner.run("manual")
    finally:
        runner_mod.download_help = orig

    # 下载失败不重试，run 仍 ok，help_diffed=0
    assert run.status == "ok"
    with env() as s:
        v = s.execute(select(Version).where(
            Version.tag == "b11518")).scalar_one()
        assert v.help_diffed == 0
        assert v.analyzed == 1


def test_no_positive_skips_help_diff(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    cache = FakeHelpCache()
    runner = make_runner(env, fetcher, FakeLLM(), cache)
    runner.run("manual")
    assert cache.saved == {}
    with env() as s:
        v = s.execute(select(Version).where(
            Version.tag == "b11518")).scalar_one()
        assert v.help_diffed == 0


def test_llm_failure_marks_partial_and_reanalyzes_later(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    llm = FakeLLM(fail=True)
    runner = make_runner(env, fetcher, llm)
    run = runner.run("manual")
    assert run.status == "partial"

    with env() as s:
        v = s.execute(select(Version).where(
            Version.tag == "b11518")).scalar_one()
        assert v.analyzed == 0
        assert v.commits_raw  # 原始数据保留

    # 下次执行补分析
    llm2 = FakeLLM()
    runner2 = make_runner(env, fetcher, llm2)
    run2 = runner2.run("manual")
    assert run2.status == "ok"
    with env() as s:
        v = s.execute(select(Version).where(
            Version.tag == "b11518")).scalar_one()
        assert v.analyzed == 1


def test_github_failure_marks_failed(env):
    fetcher = FakeFetcher(fail=True)
    runner = make_runner(env, fetcher, FakeLLM())
    run = runner.run("manual")
    assert run.status == "failed"
    assert "GitHub unreachable" in (run.error or "")


def test_reentry_rejected(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    runner = make_runner(env, fetcher, FakeLLM())
    # 模拟任务进行中（模块级锁）
    import backend.engine.runner as runner_mod
    assert runner_mod._acquire()
    try:
        with pytest.raises(BusyError):
            runner.run("manual")
    finally:
        runner_mod._release()


def test_no_new_versions_run_ok(env):
    fetcher = FakeFetcher(RELEASES, COMPARE)
    runner = make_runner(env, fetcher, FakeLLM())
    runner.run("manual")
    run2 = runner.run("manual")
    assert run2.status == "ok"
    assert json.loads(run2.versions_processed) == []


def test_skipped_tag_number_uses_actual_prev(env):
    """tag 号不连续（b11520 不存在）：上一版取 release 列表中的实际前一个。"""
    releases = [
        {"tag_name": "b11518", "published_at": "2026-10-09T01:00:00Z", "body": ""},
        {"tag_name": "b11519", "published_at": "2026-10-09T02:00:00Z", "body": ""},
        {"tag_name": "b11521", "published_at": "2026-10-09T03:00:00Z", "body": ""},
    ]
    compare = {
        "b11518": {"total_commits": 0, "commits": []},
        "b11519": {"total_commits": 0, "commits": []},
        "b11521": {"total_commits": 1, "commits": [{"sha": "d", "message": "x"}]},
    }
    fetcher = FakeFetcher(releases, compare)
    runner = make_runner(env, fetcher, FakeLLM())
    run = runner.run("manual")

    assert run.status == "ok"
    # b11521 的上一版是 b11519（b11520 不存在，不能用 b{N-1}）
    assert ("b11519", "b11521") in fetcher.compare_calls
    assert not any(c[0] == "b11520" for c in fetcher.compare_calls)
