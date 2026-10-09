"""四表模型（见 docs/design.md §6）。"""
from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Version(Base):
    """版本报告（每版一条）。"""

    __tablename__ = "versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    published_at: Mapped[str | None] = mapped_column(String)
    commit_count: Mapped[int | None] = mapped_column(Integer)
    commits_raw: Mapped[str | None] = mapped_column(Text)
    positive_items: Mapped[str | None] = mapped_column(Text)   # JSON
    launch_impact: Mapped[str | None] = mapped_column(Text)    # JSON
    suggested_flags: Mapped[str | None] = mapped_column(Text)  # JSON
    help_diffed: Mapped[int] = mapped_column(Integer, default=0)
    analyzed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)


class NewCommand(Base):
    """新增命令（单独记录）。"""

    __tablename__ = "new_commands"
    __table_args__ = (UniqueConstraint("tag", "flag", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String, nullable=False)
    flag: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str | None] = mapped_column(String)  # text | help-diff
    description: Mapped[str | None] = mapped_column(String)


class Run(Base):
    """任务执行记录。"""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[str | None] = mapped_column(String)
    ended_at: Mapped[str | None] = mapped_column(String)
    trigger: Mapped[str | None] = mapped_column(String)  # scheduled | manual
    status: Mapped[str | None] = mapped_column(String)   # ok | partial | failed
    versions_processed: Mapped[str | None] = mapped_column(Text)  # JSON 数组
    error: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    """配置（键值，页面可编辑）。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
