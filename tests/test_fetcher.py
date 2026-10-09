"""Fetcher：tag 解析、版本比较、release 列表过滤。"""
import pytest

from backend.engine.fetcher import newer_releases, tag_number


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
