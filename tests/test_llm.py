"""LLM 分析：prompt 构造、响应解析、失败处理。"""
import json

import pytest

from backend.engine.llm import LLMClient, LLMError, build_prompt

COMMITS = [
    {"sha": "abc123", "message": "CUDA: improve MTP draft acceptance"},
    {"sha": "def456", "message": "ADD: --new-flag for testing"},
]
LAUNCH_CMD = "llama-server.exe -m model.gguf --flash-attn on --spec-type draft-mtp"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload=None, exc=None):
        self._payload = payload
        self._exc = exc
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self._exc:
            raise self._exc
        return FakeResponse(self._payload)


def _payload(content: str):
    return {
        "choices": [{"message": {"content": content}}],
    }


def test_build_prompt_contains_inputs():
    prompt = build_prompt(COMMITS, LAUNCH_CMD)
    assert "abc123" in prompt
    assert "--flash-attn on" in prompt
    assert "positive" in prompt.lower() or "正提升" in prompt


def test_parse_success():
    client = FakeClient(_payload(json.dumps({
        "has_positive": True,
        "positive_items": [{"item": "MTP 性能改进", "reason": "与用户 draft-mtp 配置相关"}],
        "launch_impact": {"flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": "无影响"},
        "suggested_flags": [{"flag": "--new-flag", "reason": "测试用"}],
    })))
    result = LLMClient(client).analyze(COMMITS, LAUNCH_CMD)
    assert result["has_positive"] is True
    assert result["positive_items"][0]["item"] == "MTP 性能改进"
    assert result["suggested_flags"][0]["flag"] == "--new-flag"
    assert client.calls[0][0].endswith("/v1/chat/completions")


def test_parse_no_positive():
    client = FakeClient(_payload(json.dumps({
        "has_positive": False,
        "positive_items": [],
        "launch_impact": {"flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": "纯重构"},
        "suggested_flags": [],
    })))
    result = LLMClient(client).analyze(COMMITS, LAUNCH_CMD)
    assert result["has_positive"] is False
    assert result["positive_items"] == []


def test_parse_json_in_markdown_fence():
    client = FakeClient(_payload("```json\n" + json.dumps({
        "has_positive": False, "positive_items": [],
        "launch_impact": {"flags_removed": [], "flags_renamed": [], "default_changes": [], "notes": ""},
        "suggested_flags": [],
    }) + "\n```"))
    result = LLMClient(client).analyze(COMMITS, LAUNCH_CMD)
    assert result["has_positive"] is False


def test_http_error_raises_llm_error():
    client = FakeClient(exc=RuntimeError("HTTP 500"))
    with pytest.raises(LLMError):
        LLMClient(client).analyze(COMMITS, LAUNCH_CMD)


def test_malformed_json_raises_llm_error():
    client = FakeClient(_payload("这不是 JSON"))
    with pytest.raises(LLMError):
        LLMClient(client).analyze(COMMITS, LAUNCH_CMD)


def test_missing_choices_raises_llm_error():
    client = FakeClient({"choices": []})
    with pytest.raises(LLMError):
        LLMClient(client).analyze(COMMITS, LAUNCH_CMD)
