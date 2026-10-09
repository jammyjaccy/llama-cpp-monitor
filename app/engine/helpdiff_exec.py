"""help-diff 执行器：下载 Windows 二进制、跑 --help、缓存 help 文本。

只保留上一版 help 文本（每版一个 .txt），zip 用完即删。
缓存目录：H:\\data\\llamacpp-monitor\\helpcache
"""
import os
import subprocess
import tempfile
import zipfile

from app.engine.fetcher import tag_number

CACHE_DIR = r"H:\data\llamacpp-monitor\helpcache"
HELP_TIMEOUT = 30


class HelpDiffError(Exception):
    """二进制下载/执行失败。"""


class HelpCache:
    def __init__(self, root: str = CACHE_DIR):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, tag: str) -> str:
        return os.path.join(self.root, f"{tag}.help.txt")

    def load_help(self, tag: str) -> str:
        path = self._path(tag)
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def save_help(self, tag: str, text: str) -> None:
        with open(self._path(tag), "w", encoding="utf-8") as f:
            f.write(text)

    def latest_tag(self) -> str | None:
        """已缓存 help 文本中数字最大的 tag（即「上一版」）。"""
        tags = [
            f[:-len(".help.txt")]
            for f in os.listdir(self.root)
            if f.endswith(".help.txt")
        ]
        valid = []
        for t in tags:
            try:
                tag_number(t)
            except ValueError:
                continue
            valid.append(t)
        if not valid:
            return None
        return max(valid, key=tag_number)


def run_help(binary_path: str) -> str:
    """执行二进制 --help，合并 stdout/stderr 返回。退出码非 0 且无输出视为失败（M3）。"""
    try:
        proc = subprocess.run(
            [binary_path, "--help"],
            capture_output=True,
            timeout=HELP_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HelpDiffError(f"--help execution failed: {e}") from e
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    text = out if out.strip() else err
    if proc.returncode != 0 and not text.strip():
        raise HelpDiffError(f"--help exited {proc.returncode} with no output")
    return text


TARGET_EXE = "llama-server.exe"


def extract_binary(zip_path: str, extract_dir: str) -> str:
    """解压 zip，返回目标 .exe（llama-server.exe）的路径；缺失时回退任意 .exe（M2）。"""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    fallback: str | None = None
    for root, _dirs, files in os.walk(extract_dir):
        for name in files:
            if not name.endswith(".exe"):
                continue
            if name == TARGET_EXE:
                return os.path.join(root, name)
            if fallback is None:
                fallback = os.path.join(root, name)
    if fallback is not None:
        return fallback
    raise HelpDiffError(f"no {TARGET_EXE} (or any .exe) found in archive")


def download_help(fetcher, tag: str, cache: HelpCache) -> str:
    """下载该版 Windows 二进制并缓存其 --help 文本。失败抛 HelpDiffError（不重试）。"""
    url = fetcher.download_url(tag)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "bin.zip")
        with fetcher._client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        exe = extract_binary(zip_path, tmp)
        help_text = run_help(exe)
    cache.save_help(tag, help_text)
    return help_text
