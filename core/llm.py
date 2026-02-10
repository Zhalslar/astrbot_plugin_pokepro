import json

from astrbot.api import logger
from astrbot.core.db.po import Persona, Personality
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context

from .utils import get_nickname
from .config import PluginConfig


class LLMService:
    def __init__(self, context: Context, config: PluginConfig):
        self.context = context
        self.cfg = config

    async def get_respond(
        self, event: AiocqhttpMessageEvent, prompt_template: str
    ) -> str | None:
        """调用llm回复"""
        umo = event.unified_msg_origin

        # 获取当前会话上下文
        conv_mgr = self.context.conversation_manager
        curr_cid = await conv_mgr.get_curr_conversation_id(umo)
        if not curr_cid:
            return None
        conversation = await conv_mgr.get_conversation(umo, curr_cid)
        if not conversation:
            return None
        contexts = json.loads(conversation.history)

        # 获取当前人格提示词
        using_provider = self.context.get_using_provider(umo)
        if not using_provider:
            return None

        try:
            persona_id = conversation.persona_id
            persona: Persona = await self.context.persona_manager.get_persona(
                persona_id=persona_id  # type: ignore
            )
            system_prompt = persona.system_prompt
        except ValueError:
            # 回退到默认人格
            personality: Personality = (
                await self.context.persona_manager.get_default_persona_v3(umo=umo)
            )
            system_prompt = personality["prompt"]

        # 获取提示词
        username = await get_nickname(
            event.bot, event.get_group_id(), event.get_sender_id()
        )
        prompt = prompt_template.format(username=username)

        # 调用llm
        try:
            logger.debug(f"[戳一戳] LLM 调用：{prompt}")
            llm_response = await using_provider.text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
                contexts=contexts,
            )
            return llm_response.completion_text

        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return None
