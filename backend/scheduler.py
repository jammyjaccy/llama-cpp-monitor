"""APScheduler 内置调度（ADR-0002）。

间隔来自 settings.interval_minutes，页面改间隔后调用 reschedule 生效。
"""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_job_id = "monitor-run"


class MonitorScheduler:
    def __init__(self, run_func):
        self._scheduler = BackgroundScheduler()
        self._run_func = run_func

    def start(self, interval_minutes: int) -> None:
        self.reschedule(interval_minutes)
        self._scheduler.start()

    def reschedule(self, interval_minutes: int) -> None:
        self._scheduler.add_job(
            self._run_func,
            IntervalTrigger(minutes=interval_minutes),
            id=_job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )

    def next_run_time(self) -> datetime | None:
        """透传当前 job 的 next_run_time；job 不存在或调度器未启动时返回 None。

        注意：APScheduler 默认用系统本地时区计算，返回的是带本地时区信息的 datetime，
        消费方须显式转 UTC（见 main.get_schedule）。
        """
        if not self._scheduler.running:
            return None
        job = self._scheduler.get_job(_job_id)
        if job is None:
            return None
        return job.next_run_time

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
