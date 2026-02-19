import asyncio
from collections.abc import Sequence

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig


class PokeSender:
    def __init__(self, config: PluginConfig):
        self.cfg = config

    # ========= 内部工具 =========

    @staticmethod
    def _normalize_id(value: int | str | None) -> int | None:
        """规范化 ID：
        - None / 空字符串 / 0 → None
        - 非数字 → 抛异常
        """
        if value is None:
            return None

        if isinstance(value, int):
            return value if value != 0 else None

        value = str(value).strip()
        if not value:
            return None

        if not value.isdigit():
            raise ValueError("ID 必须为整数")

        result = int(value)
        return result if result != 0 else None

    # ========= 核心方法 =========

    @classmethod
    async def poke_func(
        cls,
        client: CQHttp,
        user_id: int | str,
        group_id: int | str | None = None,
    ):
        normalized_user_id = cls._normalize_id(user_id)
        if normalized_user_id is None:
            raise ValueError("user_id 不能为空或 0")

        normalized_group_id = cls._normalize_id(group_id)

        if normalized_group_id is not None:
            await client.group_poke(
                group_id=normalized_group_id,
                user_id=normalized_user_id,
            )
        else:
            await client.friend_poke(user_id=normalized_user_id)

    # ========= 事件发送 =========

    async def event_send(
        self,
        event: AiocqhttpMessageEvent,
        *,
        target_ids: Sequence[str | int],
        times: int = 1,
    ):
        """从事件发送戳一戳"""
        if not target_ids:
            return

        group_id = event.get_group_id()

        for tid in target_ids:
            for _ in range(times):
                try:
                    await self.poke_func(
                        client=event.bot,
                        user_id=tid,
                        group_id=group_id,
                    )
                except Exception as e:
                    logger.warning(f"戳一戳失败 user_id={tid}: {e}")

                await asyncio.sleep(self.cfg.poke_interval)

    # ========= 直接 client 发送 =========

    async def client_send(
        self,
        client: CQHttp,
        *,
        target_ids: Sequence[str | int],
        group_id: str | int | None = None,
        times: int = 1,
    ):
        """直接使用 client 发送戳一戳"""
        if not target_ids:
            return

        for tid in target_ids:
            for _ in range(times):
                try:
                    await self.poke_func(
                        client=client,
                        user_id=tid,
                        group_id=group_id,
                    )
                except Exception as e:
                    logger.warning(f"戳一戳失败 user_id={tid}: {e}")

                await asyncio.sleep(self.cfg.poke_interval)
