"""SQLite 引擎与会话管理。

DB 路径：H:\\data\\llamacpp-monitor\\monitor.db（遵守全局数据文件存储约束）。
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_DIR = r"H:\data\llamacpp-monitor"
DB_PATH = os.path.join(DB_DIR, "monitor.db")


class Base(DeclarativeBase):
    pass


def make_engine(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)


def init_db() -> None:
    from backend import models  # noqa: F401  确保模型注册

    Base.metadata.create_all(engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """SQLite 对已有库不自动加列：create_all 只建新表，已有 monitor.db 不会长出新增列。

    启动时幂等补列（ADR-0007）：PRAGMA table_info 检测缺列则 ALTER TABLE ADD COLUMN，
    免手工、可重复执行。仅补可空列（新增列均为 Mapped[str | None]，ALTER 默认允许 NULL）。
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    inspector = sa_inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            col_type = col.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}"))


def get_session() -> Session:
    return SessionLocal()
