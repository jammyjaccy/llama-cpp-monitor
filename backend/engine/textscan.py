"""文本扫描：从 commit/release 文本中提取新增命令行 flag。

匹配 ADD/ADDED 类字样后紧跟的 --xxx 序列（参见 GLOSSARY「新增命令」的文本来源）。
"""
import re

# ADD: --xxx / add --xxx / Added --xxx —— 动词后（可隔标点、and 等）的 flag
_ADD_RE = re.compile(r"\badd(?:ed|ing)?\b[^\n]*", re.IGNORECASE)
_FLAG_RE = re.compile(r"--([A-Za-z][A-Za-z0-9_-]*)")


def scan_new_flags(messages: list[str]) -> list[str]:
    """扫描 commit/release 文本，返回按字母序去重后的新增 flag 名（不含 --）。"""
    found: set[str] = set()
    for msg in messages:
        for chunk in _ADD_RE.findall(msg):
            for flag in _FLAG_RE.findall(chunk):
                found.add(flag)
    return sorted(found)
