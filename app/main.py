"""FastAPI 应用入口：REST API + 静态前端托管 + 内置调度。

仅绑定 127.0.0.1，无认证（design §4）。
"""
import json
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app import config, database
from app.engine.fetcher import Fetcher
from app.engine.helpdiff_exec import HelpCache
from app.engine.llm import LLMClient
from app.engine.runner import BusyError, Runner
from app.models import NewCommand, Run, Version
from app.scheduler import MonitorScheduler
from app.schemas import (
    RunOut,
    SettingsOut,
    SettingsUpdate,
    VersionDetailOut,
    VersionOut,
)

_scheduler: MonitorScheduler | None = None
_run_thread: threading.Thread | None = None
_trigger_lock = threading.Lock()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    database.init_db()
    with database.get_session() as db:
        s = config.load_settings(db)
    global _scheduler
    _scheduler = MonitorScheduler(lambda: _run_monitor("scheduled"))
    _scheduler.start(s.interval_minutes)
    yield
    if _scheduler:
        _scheduler.shutdown()


app = FastAPI(title="llama-cpp-monitor", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 引擎组装 ----------

def _build_runner() -> Runner:
    """每次执行按当前配置组装（代理/模型可页面修改）。"""
    with database.get_session() as db:
        s = config.load_settings(db)
    fetcher = Fetcher(proxy=s.proxy)
    llm = LLMClient(base_url=s.model_base_url, api_key=s.model_api_key, model=s.model_name)
    return Runner(
        db_factory=database.get_session,
        fetcher=fetcher,
        llm=llm,
        help_cache=HelpCache(),
    )


def _run_monitor(trigger: str) -> None:
    runner = _build_runner()
    try:
        runner.run(trigger)
    except Exception:
        pass  # run 状态已在 runner 内记录
    finally:
        for c in (runner.fetcher, runner.llm):
            try:
                c.close()
            except Exception:
                pass


def _run_monitor_with_row(run_id: int) -> None:
    """后台执行：runner 复用已创建的 run 行（手动触发路径）。"""
    runner = _build_runner()
    try:
        runner.run_with_row(run_id, "manual")
    except BusyError:
        # 极端竞态：检查后定时任务抢了锁 -> 把已建 run 行落为 failed，避免永久卡 running
        _mark_run_failed(run_id, "任务进行中，本次触发未执行")
    except Exception:
        pass  # 状态已落库（M1 兜底）；此处仅避免线程静默崩溃
    finally:
        for c in (runner.fetcher, runner.llm):
            try:
                c.close()
            except Exception:
                pass


# ---------- REST API ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/runs", response_model=list[RunOut])
def list_runs(limit: int = 50):
    limit = min(max(1, limit), 500)  # L6：限制上限，避免一次拉全表
    with database.get_session() as db:
        rows = db.execute(select(Run).order_by(Run.id.desc()).limit(limit)).scalars().all()
        return [_run_out(r) for r in rows]


@app.post("/api/runs/trigger", response_model=RunOut)
def trigger_run():
    """手动触发。任务在后台线程执行，立即返回 run 记录（status=running）。

    M5：加锁消除 check-then-act 竞态；以 Runner.is_busy()（模块级锁）为权威判断，
    覆盖定时任务与手动任务两条路径。
    """
    global _run_thread
    with _trigger_lock:
        if Runner.is_busy():
            raise HTTPException(status_code=409, detail="任务进行中，请稍后再试")
        run = _new_run_row("manual")
        _run_thread = threading.Thread(
            target=_run_monitor_with_row, args=(run.id,), daemon=True)
        _run_thread.start()
    return _run_out(run)


@app.get("/api/reports", response_model=list[VersionOut])
def list_reports(page: int = 1, page_size: int = 20):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    with database.get_session() as db:
        rows = db.execute(
            select(Version).order_by(Version.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        return [_version_out(v) for v in rows]


@app.get("/api/reports/total")
def reports_total():
    from sqlalchemy import func
    with database.get_session() as db:
        return {"total": db.execute(select(func.count(Version.id))).scalar_one()}


@app.get("/api/reports/{tag}", response_model=VersionDetailOut)
def report_detail(tag: str):
    with database.get_session() as db:
        v = db.execute(select(Version).where(Version.tag == tag)).scalar_one_or_none()
        if v is None:
            raise HTTPException(status_code=404, detail=f"version {tag} not found")
        cmds = db.execute(
            select(NewCommand).where(NewCommand.tag == tag).order_by(NewCommand.flag)
        ).scalars().all()
        out = _version_out(v)
        out["commits_raw"] = json.loads(v.commits_raw) if v.commits_raw else []
        out["new_commands"] = [_command_out(c) for c in cmds]
        return out


@app.get("/api/settings", response_model=SettingsOut)
def get_settings():
    with database.get_session() as db:
        s = config.load_settings(db)
        return SettingsOut(**s.__dict__)


@app.put("/api/settings", response_model=SettingsOut)
def put_settings(update: SettingsUpdate):
    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    try:
        with database.get_session() as db:
            s = config.update_settings(db, changes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 间隔变更即时生效
    if "interval_minutes" in changes and _scheduler:
        _scheduler.reschedule(int(changes["interval_minutes"]))
    return SettingsOut(**s.__dict__)


# ---------- 序列化 ----------

def _run_out(r: Run) -> dict:
    return {
        "id": r.id,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
        "trigger": r.trigger,
        "status": r.status,
        "versions_processed": json.loads(r.versions_processed) if r.versions_processed else [],
        "error": r.error,
    }


def _version_out(v: Version) -> dict:
    return {
        "id": v.id,
        "tag": v.tag,
        "published_at": v.published_at,
        "commit_count": v.commit_count,
        "positive_items": json.loads(v.positive_items) if v.positive_items else [],
        "launch_impact": json.loads(v.launch_impact) if v.launch_impact else {},
        "suggested_flags": json.loads(v.suggested_flags) if v.suggested_flags else [],
        "help_diffed": v.help_diffed,
        "analyzed": v.analyzed,
        "created_at": v.created_at,
    }


def _command_out(c: NewCommand) -> dict:
    return {
        "id": c.id,
        "tag": c.tag,
        "flag": c.flag,
        "source": c.source,
        "description": c.description,
    }


def _new_run_row(trigger: str) -> Run:
    from app.models import utcnow
    with database.get_session() as db:
        run = Run(trigger=trigger, status="running", started_at=utcnow())
        db.add(run)
        db.commit()
        return run


def _mark_run_failed(run_id: int, error: str) -> None:
    from app.models import utcnow
    with database.get_session() as db:
        run = db.get(Run, run_id)
        if run and run.status == "running":
            run.status = "failed"
            run.ended_at = utcnow()
            run.error = error
            db.commit()


# ---------- 前端静态托管 ----------

_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")


def _resolve_spa_file(path: str) -> str | None:
    """解析 SPA 静态文件真实路径（M4：防 ../ 路径穿越）。

    仅当 realpath 位于 dist 目录内且为文件时返回；否则 None（回退 index.html）。
    """
    if not path:
        return None
    base = os.path.realpath(_FRONTEND_DIST)
    file_path = os.path.realpath(os.path.join(base, path))
    if file_path.startswith(base + os.sep) and os.path.isfile(file_path):
        return file_path
    return None


if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        """SPA 回退：非 API 路由返回 index.html。"""
        file_path = _resolve_spa_file(path)
        if file_path:
            return FileResponse(file_path)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
