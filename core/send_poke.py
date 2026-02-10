import asyncio
from aiocqhttp import CQHttp
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig


class PokeSender:
    def __init__(self, config: PluginConfig) -> None:
        self.cfg = config
        self.self_id = "self_id"

    @staticmethod
    async def poke_func(
        client: CQHttp,
        user_id: int,
        group_id: int | None = None,
    ):
        if group_id:
            await client.group_poke(group_id=int(group_id), user_id=user_id)
        else:
            await client.friend_poke(user_id=user_id)

    async def event_send(
        self,
        event: AiocqhttpMessageEvent,
        *,
        target_id: list | str | int,
        times: int = 1,
    ):
        """发送戳一戳"""
        group_id = int(event.get_group_id())
        self_id = int(event.get_self_id())
        self.self_id = self_id

        if isinstance(target_id, str | int):
            target_ids = [target_id]

        # 去重, 忽略自己
        target_ids = list(
            dict.fromkeys(
                int(tid)
                for tid in target_ids
                if str(tid).isdigit() and int(tid) != self_id
            )
        )

        try:
            for tid in target_ids:
                for _ in range(times):
                    await self.poke_func(
                        client=event.bot, user_id=tid, group_id=group_id
                    )
                    await asyncio.sleep(self.cfg.poke_interval)
        except Exception as e:
            logger.error(f"发送戳一戳失败：{e}")

    async def client_send(
        self,
        client: CQHttp,
        *,
        target_id: list | str | int,
        group_id: str | int | None = None,
        times: int = 1,
    ):
        """发送戳一戳"""

        if isinstance(target_id, str | int):
            target_ids = [target_id]

        target_ids = list(
            dict.fromkeys(
                int(tid)
                for tid in target_ids
                if str(tid).isdigit() and int(tid) != self.self_id
            )
        )
        group_id = int(group_id) if group_id else None

        try:
            for tid in target_ids:
                for _ in range(times):
                    await self.poke_func(client, user_id=tid, group_id=group_id)
                    await asyncio.sleep(self.cfg.poke_interval)
        except Exception as e:
            logger.error(f"发送戳一戳失败：{e}")
