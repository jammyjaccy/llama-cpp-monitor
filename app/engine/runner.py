"""增量任务编排（design §5.1）。

一次执行：找新版本 -> 升序逐版处理（compare / 文本扫描 / LLM 分析 / 条件 help-diff）
-> 落 versions / new_commands -> 记 run。重入直接拒绝（BusyError）。
"""
import json
import threading

from sqlalchemy import select

from app import config
from app.engine import helpdiff
from app.engine.fetcher import newer_releases, tag_number
from app.engine.helpdiff_exec import HelpCache, download_help
from app.engine.llm import LLMError
from app.engine.textscan import scan_new_flags
from app.models import NewCommand, Run, Version, utcnow


class BusyError(Exception):
    """上一次任务仍在执行。"""


# 进程级互斥：每次执行都新建 Runner（main._build_runner），实例级锁无法跨定时/手动路径互斥
_GLOBAL_LOCK = threading.Lock()
_GLOBAL_RUNNING = False


def _acquire() -> bool:
    global _GLOBAL_RUNNING
    with _GLOBAL_LOCK:
        if _GLOBAL_RUNNING:
            return False
        _GLOBAL_RUNNING = True
        return True


def _release() -> None:
    global _GLOBAL_RUNNING
    with _GLOBAL_LOCK:
        _GLOBAL_RUNNING = False


class Runner:
    def __init__(self, db_factory, fetcher, llm, help_cache: HelpCache | None = None):
        self.db_factory = db_factory
        self.fetcher = fetcher
        self.llm = llm
        self.help_cache = help_cache or HelpCache()

    def run(self, trigger: str = "manual") -> Run:
        """创建 run 行并执行（定时路径）。忙时不建行，直接抛 BusyError（H3）。"""
        if not _acquire():
            raise BusyError("任务进行中")
        try:
            run = Run(trigger=trigger, status="running", started_at=utcnow())
            with self.db_factory() as db:
                db.add(run)
                db.commit()
                run_id = run.id
            self._execute(run_id, trigger)
        finally:
            _release()
        return self._get_run(run_id)

    def run_with_row(self, run_id: int, trigger: str = "manual") -> None:
        """对已存在的 run 行执行（手动触发路径：行先由 API 创建）。忙时抛 BusyError。"""
        if not _acquire():
            raise BusyError("任务进行中")
        try:
            self._execute(run_id, trigger)
        finally:
            _release()

    @staticmethod
    def is_busy() -> bool:
        return _GLOBAL_RUNNING

    # ---- 内部 ----

    def _get_run(self, run_id: int) -> Run:
        with self.db_factory() as db:
            return db.get(Run, run_id)

    def _execute(self, run_id: int, trigger: str) -> None:
        processed: list[str] = []
        partial = False
        try:
            releases = self.fetcher.list_releases()
        except Exception as e:
            self._finish(run_id, "failed", [], f"GitHub 不可达: {e}")
            return

        try:
            with self.db_factory() as db:
                settings = config.load_settings(db)
                max_tag = self._max_processed_tag(db)
                baseline = settings.baseline_tag

            # 严格大于下界（max(baseline, 已处理最大)）的版本，升序（复用 fetcher 纯函数）
            targets = newer_releases(
                releases,
                baseline=baseline,
                processed_max=max_tag,
            )

            # tag 号不连续（如缺 b11522）：上一版取 release 列表中的实际前一个 tag
            prev_map: dict[str, str | None] = {}
            all_tags = sorted(
                (r["tag_name"] for r in releases if _safe_num(r.get("tag_name"))),
                key=tag_number,
            )
            for i, t in enumerate(all_tags):
                prev_map[t] = all_tags[i - 1] if i > 0 else None

            # 补分析：已入库但 analyzed=0 的版本（LLM 上次不可用）
            to_reanalyze = [t for t in self._unanalyzed_tags()
                            if not any(r["tag_name"] == t for r in targets)]

            for rel in targets:
                if self._process_version(rel["tag_name"], rel, settings, prev_map):
                    processed.append(rel["tag_name"])
                else:
                    partial = True

            for tag in to_reanalyze:
                if self._process_version(tag, None, settings, prev_map):
                    processed.append(tag)
                else:
                    partial = True

            self._finish(run_id, "ok" if not partial else "partial", processed, None)
        except Exception as e:
            # 顶层兜底：任何意外异常都落 run 状态，避免行永久卡 "running"（M1）
            self._finish(run_id, "failed", processed, f"执行异常: {e}")

    def _max_processed_tag(self, db) -> str | None:
        return db.execute(
            select(Version.tag).order_by(Version.id.desc()).limit(1)
        ).scalar_one_or_none()

    def _unanalyzed_tags(self) -> list[str]:
        with self.db_factory() as db:
            return list(db.execute(
                select(Version.tag).where(Version.analyzed == 0)
            ).scalars())

    def _process_version(self, tag: str, rel: dict | None, settings,
                         prev_map: dict[str, str | None] | None = None) -> bool:
        """处理单版。True=成功，False=分析失败（下次补）。"""
        prev_map = prev_map or {}
        prev = prev_map.get(tag) or f"b{tag_number(tag) - 1}"
        with self.db_factory() as db:
            existing = db.execute(select(Version).where(Version.tag == tag)).scalar_one_or_none()
            if existing is None:
                existing = Version(tag=tag, published_at=(rel or {}).get("published_at"))
                db.add(existing)
                db.commit()

            # compare 拉完整 commit 列表（缺失时补拉）
            if existing.commits_raw is None:
                try:
                    data = self.fetcher.compare(prev, tag)
                except Exception:
                    # 该版失败：版本行已入库（原始数据留空），下次执行补
                    return False
                existing.commit_count = data.get("total_commits")
                existing.commits_raw = json.dumps(data.get("commits", []), ensure_ascii=False)
                db.commit()

            # 文本扫描（幂等：UNIQUE(tag, flag, source) 去重）
            for flag in scan_new_flags(_commit_messages(existing.commits_raw)):
                self._upsert_command(db, tag, flag, "text")
            db.commit()

            # LLM 分析（可补）
            if existing.analyzed != 1:
                try:
                    commits = json.loads(existing.commits_raw)
                    result = self.llm.analyze(commits, settings.launch_command, tag)
                except LLMError:
                    return False

                existing.positive_items = json.dumps(result.get("positive_items", []), ensure_ascii=False)
                existing.launch_impact = json.dumps(result.get("launch_impact", {}), ensure_ascii=False)
                existing.suggested_flags = json.dumps(result.get("suggested_flags", []), ensure_ascii=False)
                existing.analyzed = 1

                # 条件 help-diff（ADR-0003）：仅当有正提升
                if result.get("has_positive"):
                    self._conditional_help_diff(db, tag, prev)

                db.commit()

            return True

    def _conditional_help_diff(self, db, tag: str, prev: str) -> None:
        """失败不重试，help_diffed 保持 0（页面标注「help diff 未完成」）。"""
        try:
            prev_text = self.help_cache.load_help(prev)
            if not prev_text:
                # 上一版 help 未缓存：先补下载建立基线
                prev_text = download_help(self.fetcher, prev, self.help_cache)
            new_text = download_help(self.fetcher, tag, self.help_cache)
        except Exception:
            return

        for item in helpdiff.diff_help_texts(prev_text, new_text):
            self._upsert_command(db, tag, item["flag"], "help-diff", item.get("description"))
        v = db.execute(select(Version).where(Version.tag == tag)).scalar_one()
        v.help_diffed = 1
        db.commit()

    @staticmethod
    def _upsert_command(db, tag: str, flag: str, source: str, description: str | None = None) -> None:
        existing = db.execute(
            select(NewCommand).where(
                NewCommand.tag == tag, NewCommand.flag == flag, NewCommand.source == source
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(NewCommand(tag=tag, flag=flag, source=source, description=description))
        elif description and not existing.description:
            existing.description = description

    def _finish(self, run_id: int, status: str, processed: list[str], error: str | None) -> None:
        with self.db_factory() as db:
            run = db.get(Run, run_id)
            run.status = status
            run.ended_at = utcnow()
            run.versions_processed = json.dumps(processed, ensure_ascii=False)
            run.error = error
            db.commit()


def _safe_num(tag: str | None) -> int | None:
    if not tag:
        return None
    try:
        return tag_number(tag)
    except ValueError:
        return None


def _commit_messages(raw: str) -> list[str]:
    """commits_raw（GitHub compare 结构）-> commit 消息列表，供文本扫描。

    compare 的 commit 消息在嵌套层 commit.message（顶层无 message 字段）。
    """
    try:
        commits = json.loads(raw)
    except json.JSONDecodeError:
        return []
    msgs = []
    for c in commits:
        if not isinstance(c, dict):
            continue
        inner = c.get("commit")
        if isinstance(inner, dict) and inner.get("message"):
            msgs.append(inner["message"])
        elif c.get("message"):
            msgs.append(c["message"])
    return msgs
