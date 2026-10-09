"""APScheduler 内置调度（ADR-0002）。

间隔来自 settings.interval_minutes，页面改间隔后调用 reschedule 生效。
"""
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

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
