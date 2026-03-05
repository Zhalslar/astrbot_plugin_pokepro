import json

from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context

from .config import PluginConfig
from .utils import get_nickname


class LLMService:
    def __init__(self, context: Context, config: PluginConfig):
        self.context = context
        self.cfg = config

    async def get_conversation(self, event: AiocqhttpMessageEvent):
        """获取或创建当前会话的 conversation 对象"""
        umo = event.unified_msg_origin
        conv_mgr = self.context.conversation_manager
        try:
            cid = await conv_mgr.get_curr_conversation_id(umo)
            if not cid:
                cid = await conv_mgr.new_conversation(umo, event.get_platform_id())
            return await conv_mgr.get_conversation(umo, cid)
        except Exception as e:
            logger.warning(f"[Pokepro] 获取 conversation 失败: {e}")
            return None

    async def build_prompt(
        self, event: AiocqhttpMessageEvent, prompt_template: str
    ) -> str:
        """构建用户 prompt"""
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )
        return prompt_template.format(username=username)
