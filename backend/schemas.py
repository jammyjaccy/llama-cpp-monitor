"""API 请求/响应模型。"""
from pydantic import BaseModel, Field


class RunOut(BaseModel):
    id: int
    started_at: str | None
    ended_at: str | None
    trigger: str | None
    status: str | None
    versions_processed: list[str] = []
    error: str | None


class VersionOut(BaseModel):
    id: int
    tag: str
    published_at: str | None
    commit_count: int | None
    positive_items: list[dict] = []
    launch_impact: dict = {}
    suggested_flags: list[dict] = []
    help_diffed: int
    analyzed: int
    created_at: str | None


class VersionDetailOut(VersionOut):
    commits_raw: list[dict] = []
    new_commands: list[dict] = []


class NewCommandOut(BaseModel):
    id: int
    tag: str
    flag: str
    source: str | None
    description: str | None


class SettingsOut(BaseModel):
    interval_minutes: int
    baseline_tag: str
    model_base_url: str
    model_api_key: str
    model_name: str
    proxy: str
    launch_command: str


class SettingsUpdate(BaseModel):
    interval_minutes: int | None = Field(None, ge=1)
    baseline_tag: str | None = None
    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str | None = None
    proxy: str | None = None
    launch_command: str | None = None
