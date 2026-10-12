"""database.init_db 启动时检测补列（ADR-0007）。

SQLite 对已有库不自动加列：create_all 只建新表，已有 monitor.db 不会长出新增列。
init_db 的 _ensure_columns 用 PRAGMA table_info 检测缺列则 ALTER TABLE ADD COLUMN。
"""
from sqlalchemy import create_engine, inspect, text

from backend import database


def _old_versions_table(engine):
    """模拟旧库：建 versions 表但不含 commit_notes 列。"""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE versions ("
            "id INTEGER PRIMARY KEY, tag VARCHAR NOT NULL UNIQUE, "
            "published_at VARCHAR, commit_count INTEGER, commits_raw TEXT, "
            "positive_items TEXT, launch_impact TEXT, suggested_flags TEXT, "
            "help_diffed INTEGER DEFAULT 0, analyzed INTEGER DEFAULT 0, "
            "created_at VARCHAR)"
        ))


def test_init_db_adds_missing_commit_notes_column(tmp_path, monkeypatch):
    """旧库（无 commit_notes 列）经 init_db 后长出该列。"""
    engine = create_engine(f"sqlite:///{tmp_path}/old.db", future=True)
    _old_versions_table(engine)
    # 确认旧库确实缺列
    before = {c["name"] for c in inspect(engine).get_columns("versions")}
    assert "commit_notes" not in before

    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    after = {c["name"] for c in inspect(engine).get_columns("versions")}
    assert "commit_notes" in after


def test_init_db_idempotent(tmp_path, monkeypatch):
    """init_db 可重复执行：已含列的库二次执行不报错、不重复加列。"""
    engine = create_engine(f"sqlite:///{tmp_path}/new.db", future=True)
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    database.init_db()  # 第二次不应抛错

    cols = [c["name"] for c in inspect(engine).get_columns("versions")]
    assert cols.count("commit_notes") == 1
