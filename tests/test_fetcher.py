"""Fetcher：tag 解析、版本比较、release 列表过滤、代理默认值。"""
import pytest

from backend import config
from backend.engine.fetcher import Fetcher, newer_releases, tag_number


def test_tag_number():
    assert tag_number("b11518") == 11518
    assert tag_number("b11514") == 11514


def test_tag_number_invalid():
    for bad in ("11518", "xb11518", "b1151x", "", "B11518"):
        with pytest.raises(ValueError):
            tag_number(bad)


def test_newer_releases_filters_and_sorts():
    releases = [
        {"tag_name": "b11520"},
        {"tag_name": "b11518"},
        {"tag_name": "b11519"},
        {"tag_name": "b11514"},  # 基线本身，不算更新
        {"tag_name": "b11513"},  # 旧版本
    ]
    result = newer_releases(releases, baseline="b11514")
    assert [r["tag_name"] for r in result] == ["b11518", "b11519", "b11520"]


def test_newer_releases_processed_max():
    releases = [
        {"tag_name": "b11521"},
        {"tag_name": "b11518"},
        {"tag_name": "b11519"},
    ]
    result = newer_releases(releases, processed_max="b11518")
    assert [r["tag_name"] for r in result] == ["b11519", "b11521"]


def test_newer_releases_no_updates():
    releases = [{"tag_name": "b11518"}]
    assert newer_releases(releases, processed_max="b11518") == []


def test_newer_releases_skips_unparseable_tags():
    releases = [{"tag_name": "v1.0"}, {"tag_name": "b11519"}]
    result = newer_releases(releases, baseline="b11514")
    assert [r["tag_name"] for r in result] == ["b11519"]


# ---- 代理默认值（ADR-0006：fetcher 构造器默认引用 .env 派生默认，无第二份硬编码）----

def test_fetcher_default_proxy_from_env(monkeypatch):
    """fetcher 不传 proxy 时取 .env 派生默认（经 _ENV_DEFAULTS 注入）。"""
    monkeypatch.setattr(config, "_ENV_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
        "proxy": "http://127.0.0.1:7897",
    })
    f = Fetcher()
    try:
        assert f.proxy == "http://127.0.0.1:7897"
    finally:
        f.close()


def test_fetcher_explicit_proxy_wins(monkeypatch):
    """显式传入 proxy 时优先于 .env 默认。"""
    monkeypatch.setattr(config, "_ENV_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
        "proxy": "http://127.0.0.1:7897",
    })
    f = Fetcher(proxy="http://127.0.0.1:9999")
    try:
        assert f.proxy == "http://127.0.0.1:9999"
    finally:
        f.close()


def test_fetcher_source_has_no_hardcoded_proxy():
    """fetcher.py 源码中不得再出现硬编码代理地址（消灭双源）。"""
    import inspect
    src = inspect.getsource(Fetcher)
    assert "127.0.0.1" not in src
