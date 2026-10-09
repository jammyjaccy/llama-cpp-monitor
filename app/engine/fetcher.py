"""GitHub Fetcher：releases 列表 + compare API（走代理）。

仓库：ggml-org/llama.cpp（旧地址 ggerganov/llama.cpp 301 跳转，代码用新地址）。
"""
import httpx

REPO = "ggml-org/llama.cpp"
API_BASE = "https://api.github.com"


def tag_number(tag: str) -> int:
    """bNNNNN -> NNNNN。非 b 前缀或非数字抛 ValueError。"""
    if not tag.startswith("b"):
        raise ValueError(f"invalid tag: {tag!r}")
    num = tag[1:]
    if not num.isdigit():
        raise ValueError(f"invalid tag: {tag!r}")
    return int(num)


def newer_releases(
    releases: list[dict],
    *,
    baseline: str | None = None,
    processed_max: str | None = None,
) -> list[dict]:
    """过滤出严格大于下界的 release，按 tag 数字升序。

    下界 = max(baseline, processed_max)；两者皆空时返回全部可解析 tag。
    不可解析的 tag（非 bNNNNN）跳过。
    """
    bounds = [n for n in (tag_number(baseline) if baseline else None,
                          tag_number(processed_max) if processed_max else None) if n is not None]
    lower = max(bounds) if bounds else 0

    result = []
    for rel in releases:
        tag = rel.get("tag_name", "")
        try:
            n = tag_number(tag)
        except ValueError:
            continue
        if n > lower:
            result.append(rel)
    result.sort(key=lambda r: tag_number(r["tag_name"]))
    return result


class Fetcher:
    """GitHub API 客户端。代理地址可配置（默认 http://127.0.0.1:7981）。"""

    def __init__(self, proxy: str = "http://127.0.0.1:7981", token: str | None = None):
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=API_BASE,
            headers=headers,
            proxy=proxy or None,
            timeout=60,
        )

    def close(self) -> None:
        self._client.close()

    def list_releases(self, per_page: int = 100) -> list[dict]:
        """最近 per_page 条 release（新到旧）。"""
        resp = self._client.get(f"/repos/{REPO}/releases", params={"per_page": per_page})
        resp.raise_for_status()
        return resp.json()

    def compare(self, prev_tag: str, tag: str) -> dict:
        """compare 上一版...本版，返回完整 commit 列表（含 total_commits）。"""
        resp = self._client.get(f"/repos/{REPO}/compare/{prev_tag}...{tag}")
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in ("ahead", "identical", None):
            raise ValueError(f"compare {prev_tag}...{tag} status={data.get('status')}")
        return data

    def download_url(self, tag: str, platform: str = "win-cuda-12.4-x64") -> str:
        """该版 Windows 二进制 zip 的下载链接（release assets 中匹配平台后缀）。"""
        resp = self._client.get(f"/repos/{REPO}/releases/tags/{tag}")
        resp.raise_for_status()
        assets = resp.json().get("assets", [])
        pattern = f"-bin-{platform}.zip"
        for asset in assets:
            if asset["name"].endswith(pattern):
                return asset["browser_download_url"]
        raise FileNotFoundError(f"asset for {tag} ({platform}) not found")
