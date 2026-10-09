"""help-diff：两份 --help 文本 diff 出新增 flag。

flag 行形如 `  --name  description...`（缩进可变）。基线为空文本时所有 flag 算新增。
"""
import difflib
import re

# llama.cpp help 格式：`  --flag TYPE  Description`，flag 名后跟的参数/描述以单空格分隔
_FLAG_LINE_RE = re.compile(r"^\s{1,16}--([A-Za-z][A-Za-z0-9_-]*)(?:\s+(.*))?$")


def _parse_flags(text: str) -> dict[str, str]:
    """help 文本 -> {flag: description}。行内提到 flag 的正文行（无行首缩进）不算。"""
    flags: dict[str, str] = {}
    for line in text.splitlines():
        m = _FLAG_LINE_RE.match(line)
        if m:
            flags.setdefault(m.group(1), (m.group(2) or "").strip())
    return flags


def diff_help_texts(old_text: str, new_text: str) -> list[dict]:
    """返回 new 中新增的 flag：[{"flag": name, "description": desc}]。"""
    old_flags = _parse_flags(old_text)
    new_flags = _parse_flags(new_text)
    added = [name for name in new_flags if name not in old_flags]
    added.sort()
    return [{"flag": name, "description": new_flags[name]} for name in added]


def summarize_diff(old_text: str, new_text: str) -> str:
    """生成可读的 unified diff 摘要（用于页面展示）。"""
    return "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="old --help",
            tofile="new --help",
            lineterm="",
        )
    )
