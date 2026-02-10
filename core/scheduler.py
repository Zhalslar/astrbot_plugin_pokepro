# core/scheduler.py
from __future__ import annotations

from aiocqhttp import CQHttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger

from .send_poke import PokeSender
from .config import PluginConfig


class PokeScheduler:
    """
    定时戳调度器
    """

    def __init__(self, config: PluginConfig, sender: PokeSender):
        self.cfg = config.scheduler
        self.cron = self.cfg.cron
        self.target_list = config.target_list
        self.sender = sender

        self._scheduler = AsyncIOScheduler()
        self._started = False
        self._job_id = "scheduler_poke"

        self.client: CQHttp | None = None

    def set_client(self, client: CQHttp):
        if not self.client:
            self.client = client

    # ========== 生命周期 ==========

    def start(self) -> None:
        if self._started:
            return

        self._register_job()
        self._scheduler.start()
        self._started = True

    def shutdown(self) -> None:
        if not self._started:
            return

        self._scheduler.shutdown(wait=False)
        self._started = False

    def _register_job(self):
        try:
            trigger = CronTrigger.from_crontab(self.cron)
        except Exception as e:
            logger.error(f"cron 无效: {self.cron}, {e}")
            return
        self._scheduler.add_job(
            self._on_trigger,
            trigger=trigger,
            id=self._job_id,
            replace_existing=True,
        )
        logger.debug(f"已注册定时戳任务，Cron: {self.cron}")

    async def _on_trigger(self) -> None:
        if not self.client:
            return
        for target in self.target_list:
            gid, uid = target
            await self.sender.client_send(
                client=self.client,
                target_id=uid,
                group_id=gid,
                times=self.cfg.times,
            )
