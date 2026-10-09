"""LLM 分析：正提升判断 + 启动命令影响分析。

OpenAI 兼容接口（/v1/chat/completions），httpx 直调，不引 openai SDK。
"""
import json
import re

import httpx

PROMPT_TEMPLATE = """你是 llama.cpp 版本更新分析助手。用户本地运行环境：
- 3×CUDA（tensor-split 30/34/0，split-mode layer）
- draft-mtp 投机解码（spec-draft-n-max 3，q4_0 kv）
- flash-attn on，ctx 139072，ctx-checkpoints 32，load-mode dio

用户启动命令：
{launch_command}

以下是 llama.cpp 版本 {tag} 的完整 commit 列表：
{commits}

请分析并输出 JSON（不要输出其他内容），schema：
{{
  "has_positive": bool,          // 对用户本地环境是否有正提升
  "positive_items": [{{"item": str, "reason": str}}],  // 有正提升的条目及理由；无则空数组
  "launch_impact": {{
    "flags_removed": [str],      // 用户所用 flag 中被删除的
    "flags_renamed": [str],      // 被改名的（写 旧名->新名）
    "default_changes": [str],    // 默认值变化且影响用户用法的
    "notes": str                 // 其他影响说明，无则空字符串
  }},
  "suggested_flags": [{{"flag": str, "reason": str}}]  // 建议用户加上的新 flag；无则空数组
}}

正提升判定标准：
- 算：性能改进（尤其 CUDA/MTP 投机解码/flash-attn/内存，与用户配置相关）；用户启动命令可用的新功能；修掉影响用户这类用法的 bug
- 不算：纯重构、CI、文档、用户不用的后端（Vulkan/SYCL/Android/OpenVINO 等）
"""


class LLMError(Exception):
    """LLM 调用失败（网络/HTTP/解析）。"""


def _commit_message(c: dict) -> str:
    """取 commit 消息：GitHub compare 在嵌套层 commit.message，兼容扁平 message。"""
    inner = c.get("commit")
    if isinstance(inner, dict) and inner.get("message"):
        return inner["message"]
    return c.get("message", "")


def build_prompt(commits: list[dict], launch_command: str, tag: str = "") -> str:
    lines = []
    for c in commits:
        msg = _commit_message(c).splitlines()[0] if _commit_message(c) else "(no message)"
        lines.append(f"- {c.get('sha', '?')[:7]} {msg}")
    return PROMPT_TEMPLATE.format(
        launch_command=launch_command,
        commits="\n".join(lines),
        tag=tag,
    )


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍 markdown 围栏）。"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"no JSON object in LLM output: {text[:200]!r}")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from LLM: {e}") from e


class LLMClient:
    def __init__(self, client: httpx.Client | None = None,
                 base_url: str = "", api_key: str = "", model: str = ""):
        self._client = client or httpx.Client(timeout=300)
        self._owns_client = client is None
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def analyze(self, commits: list[dict], launch_command: str, tag: str = "") -> dict:
        """单版分析。返回解析后的 dict（has_positive/positive_items/launch_impact/suggested_flags）。"""
        try:
            resp = self._client.post(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": build_prompt(commits, launch_command, tag)}],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise LLMError(f"LLM request failed: {e}") from e

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("LLM returned no choices")
        return _extract_json(choices[0]["message"]["content"])
