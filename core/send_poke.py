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

    @staticmethod
    async def poke_func(
        client: CQHttp,
        user_id: int,
        group_id: int | None = None,
    ):
        if group_id is not None:
            await client.group_poke(group_id=group_id, user_id=user_id)
        else:
            await client.friend_poke(user_id=user_id)

    def _normalize_target_ids(
        self,
        target_id: list | str | int,
        *,
        self_id: int | None = None,
    ) -> list[int]:
        if isinstance(target_id, (str, int)):
            raw_ids = [target_id]
        else:
            raw_ids = target_id

        result: list[int] = []
        for tid in raw_ids:
            if str(tid).isdigit():
                tid = int(tid)
                if self_id is None or tid != self_id:
                    result.append(tid)

        # 去重但保持顺序
        return list(dict.fromkeys(result))

    async def _send_poke_loop(
        self,
        *,
        client: CQHttp,
        target_ids: list[int],
        group_id: int | None,
        times: int,
    ):
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

    async def event_send(
        self,
        event: AiocqhttpMessageEvent,
        *,
        target_id: list | str | int,
        times: int = 1,
    ):
        """从事件发送戳一戳"""

        self_id = int(event.get_self_id())
        group_id_raw = event.get_group_id()
        group_id = int(group_id_raw) if group_id_raw and str(group_id_raw).strip() else None

        target_ids = self._normalize_target_ids(
            target_id,
            self_id=self_id,
        )

        if not target_ids:
            return

        await self._send_poke_loop(
            client=event.bot,
            target_ids=target_ids,
            group_id=group_id,
            times=times,
        )

    async def client_send(
        self,
        client: CQHttp,
        *,
        target_id: list | str | int,
        group_id: str | int | None = None,
        self_id: int | None = None,
        times: int = 1,
    ):
        """直接使用 client 发送戳一戳"""

        target_ids = self._normalize_target_ids(
            target_id,
            self_id=self_id,
        )

        if not target_ids:
            return

        group_id = int(group_id) if group_id is not None else None

        await self._send_poke_loop(
            client=client,
            target_ids=target_ids,
            group_id=group_id,
            times=times,
        )
