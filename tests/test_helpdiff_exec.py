"""help-diff 执行器：help 文本缓存管理 + 二进制提取/--help 执行。"""
import subprocess
import zipfile

import pytest

from backend.engine.helpdiff_exec import (
    HelpCache,
    HelpDiffError,
    extract_binary,
    run_help,
)


def test_save_and_load(tmp_path):
    cache = HelpCache(tmp_path)
    cache.save_help("b11518", "  --help  Show help\n")
    assert cache.load_help("b11518") == "  --help  Show help\n"


def test_load_missing_returns_empty(tmp_path):
    cache = HelpCache(tmp_path)
    assert cache.load_help("b99999") == ""


def test_latest_tag_tracks_saves(tmp_path):
    cache = HelpCache(tmp_path)
    assert cache.latest_tag() is None
    cache.save_help("b11518", "a")
    cache.save_help("b11519", "b")
    assert cache.latest_tag() == "b11519"


def test_latest_tag_numeric_order(tmp_path):
    cache = HelpCache(tmp_path)
    cache.save_help("b1159", "a")
    cache.save_help("b11510", "b")
    assert cache.latest_tag() == "b11510"


def _make_zip(path, names):
    with zipfile.ZipFile(path, "w") as zf:
        for n in names:
            zf.writestr(n, b"")


def test_extract_binary_prefers_llama_server(tmp_path):
    """M2：zip 含多个 .exe 时优先取 llama-server.exe。"""
    zip_path = tmp_path / "bin.zip"
    _make_zip(zip_path, ["llama-cli.exe", "sub/llama-server.exe", "llama-bench.exe"])
    out = tmp_path / "out"
    out.mkdir()
    exe = extract_binary(str(zip_path), str(out))
    assert exe.endswith("llama-server.exe")


def test_extract_binary_falls_back_to_any_exe(tmp_path):
    """M2：无 llama-server.exe 时回退任意 .exe。"""
    zip_path = tmp_path / "bin.zip"
    _make_zip(zip_path, ["llama-cli.exe"])
    out = tmp_path / "out"
    out.mkdir()
    exe = extract_binary(str(zip_path), str(out))
    assert exe.endswith("llama-cli.exe")


def test_extract_binary_no_exe_raises(tmp_path):
    zip_path = tmp_path / "bin.zip"
    _make_zip(zip_path, ["readme.txt"])
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(HelpDiffError):
        extract_binary(str(zip_path), str(out))


def test_run_help_nonzero_no_output_raises(monkeypatch):
    """M3：退出码非 0 且无输出 -> HelpDiffError。"""
    class FakeProc:
        returncode = 1
        stdout = b""
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
    with pytest.raises(HelpDiffError):
        run_help("some.exe")


def test_run_help_nonzero_with_output_ok(tmp_path, monkeypatch):
    """M3：退出码非 0 但有输出（llama-server --help 正常返回非 0）不报错。"""
    class FakeProc:
        returncode = 1
        stdout = b"  --help  Show help\n"
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
    assert "--help" in run_help("some.exe")
