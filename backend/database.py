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


def get_session() -> Session:
    return SessionLocal()
