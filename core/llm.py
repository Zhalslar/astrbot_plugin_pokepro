import json

from astrbot.api import logger
from astrbot.core.db.po import Persona, Personality
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

    async def get_respond(
        self, event: AiocqhttpMessageEvent, prompt_template: str
    ) -> str | None:
        """调用 LLM 回复"""
        umo = event.unified_msg_origin

        contexts = await self._get_contexts(umo)
        if contexts is None:
            return None

        system_prompt = await self._get_system_prompt(umo)
        if not system_prompt:
            return None

        prompt = await self._build_prompt(event, prompt_template)

        using_provider = self.context.get_using_provider(umo)
        if not using_provider:
            return None

        try:
            logger.debug(f"[戳一戳] LLM 调用：{prompt}")
            resp = await using_provider.text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
                contexts=contexts,
            )
            return resp.completion_text
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return None

    # ========================
    # 内部方法
    # ========================

    async def _get_contexts(self, umo) -> list | None:
        """获取当前会话上下文"""
        conv_mgr = self.context.conversation_manager
        cid = await conv_mgr.get_curr_conversation_id(umo)
        if not cid:
            return None

        conversation = await conv_mgr.get_conversation(umo, cid)
        if not conversation:
            return None

        return json.loads(conversation.history)

    async def _get_system_prompt(self, umo) -> str | None:
        """获取 system prompt（优先会话人格，失败回退默认人格）"""
        conv_mgr = self.context.conversation_manager
        cid = await conv_mgr.get_curr_conversation_id(umo)
        if not cid:
            return None

        conversation = await conv_mgr.get_conversation(umo, cid)
        if not conversation:
            return None

        try:
            persona: Persona = await self.context.persona_manager.get_persona(
                persona_id=conversation.persona_id  # type: ignore
            )
            return persona.system_prompt
        except ValueError:
            personality: Personality = (
                await self.context.persona_manager.get_default_persona_v3(umo=umo)
            )
            return personality["prompt"]

    async def _build_prompt(self, event: AiocqhttpMessageEvent, template: str) -> str:
        """构建用户 prompt"""
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )
        return template.format(username=username)
