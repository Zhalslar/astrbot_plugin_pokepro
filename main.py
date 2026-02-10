from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .core.config import PluginConfig
from .core.get_poke import GetPokeHandler
from .core.utils import send_poke, get_ats, get_member_ids


class PokeproPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context)
        self.get_poke_handler = GetPokeHandler(context, self.cfg)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AiocqhttpMessageEvent):
        """监听消息"""
        # 收到自己被戳的事件
        async for msg in self.get_poke_handler.handle(event):
            yield msg

        # 关键字触发戳一戳
        if not event.is_at_or_wake_command:
            return
        if self.cfg.hit_poke_keywords(event.message_str):
            target_id = event.get_sender_id()
            await send_poke(event, target_id)

    @filter.command("戳", alias={"戳我", "戳全体成员"})
    async def on_poke_cmd(self, event: AiocqhttpMessageEvent):
        """戳 @某人/我/全体成员"""
        msg = event.message_str
        end = msg.split()[-1]
        times = int(end) if end.isdigit() else 1
        is_admin = event.is_admin()
        gid = event.get_group_id()

        # 限制非管理员戳的次数
        if not is_admin:
            times = self.cfg.get_poke_times(times)

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

        await send_poke(event, target_ids, times=times)
        event.stop_event()

