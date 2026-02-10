from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .core.config import PluginConfig
from .core.on_poke import GetPokeHandler
from .core.utils import get_ats, get_member_ids
from .core.send_poke import PokeSender
from .core.scheduler import PokeScheduler


class PokeproPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context)
        self.sender = PokeSender(self.cfg)
        self.get_poke_handler = GetPokeHandler(context, self.cfg, self.sender)
        self.scheduler = None

    async def initialize(self):
        if self.cfg.scheduler.enabled:
            self.scheduler = PokeScheduler(self.cfg, self.sender)
            self.scheduler.start()

    async def terminate(self):
        if self.scheduler:
            self.scheduler.shutdown()

    @filter.command("戳", alias={"戳我", "戳全体成员"})
    async def on_poke_cmd(self, event: AiocqhttpMessageEvent):
        """戳 @某人/我/全体成员"""
        msg = event.message_str
        end = msg.split()[-1]
        times = int(end) if end.isdigit() else 1
        times = min(self.cfg.poke_max_times, times)

        is_admin = event.is_admin()
        gid = event.get_group_id()

        # 获取目标用户ID
        target_ids = get_ats(event)
        if "我" in msg:
            target_ids.append(event.get_sender_id())
        if "全体成员" in msg and is_admin:
            target_ids = await get_member_ids(event)
        if not target_ids:
            result: dict = await event.bot.get_group_msg_history(group_id=int(gid))
            target_ids = [msg["sender"]["user_id"] for msg in result["messages"]]
        if not target_ids:
            return

        await self.sender.event_send(
            event,
            target_id=target_ids,
            times=times,
        )
        event.stop_event()

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AiocqhttpMessageEvent):
        """监听消息"""
        # 设置定时器用的客户端
        if self.scheduler:
            self.scheduler.set_client(event.bot)

        # 收到自己被戳的事件
        if self.cfg.on_poke:
            async for msg in self.get_poke_handler.handle(event):
                yield msg

        # 关键字触发戳一戳
        if event.is_at_or_wake_command and self.cfg.poke_keywords:
            if self.cfg.hit_poke_keywords(event.message_str):
                await self.sender.event_send(
                    event,
                    target_id=event.get_sender_id(),
                    times=1,
                )
