import random

from astrbot.api import logger
from astrbot.api.message_components import At, Face, Plain, Poke
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context

from .llm import LLMService
from .config import PluginConfig
from .cooldown import Cooldown
from .utils import send_poke


class GetPokeHandler:
    def __init__(self, context: Context, config: PluginConfig):
        self.context = context
        self.cfg = config
        self.llm = LLMService(context, self.cfg)
        self.cooldown = Cooldown(self.cfg)

        # 获取所有 _respond 方法（反戳：LLM：face：图库：禁言：meme：api：开盒）
        self.response_handlers = [
            self.poke_respond,
            self.llm_respond,
            self.face_respond,
            self.gallery_respond,
            self.ban_respond,
            self.meme_respond,
            self.api_respond,
            self.box_respond,
        ]

        self.weights: list[int] = self.cfg.weight_list + [1] * (
            len(self.response_handlers) - len(self.cfg.weight_list)
        )

    async def handle(self, event: AiocqhttpMessageEvent):
        """响应戳一戳事件"""
        if event.get_extra("is_poke_event"):
            return
        raw = getattr(event.message_obj, "raw_message", None)

        if (
            not raw
            or not event.message_obj.message
            or not isinstance(event.message_obj.message[0], Poke)
        ):
            return

        target_id: int = raw.get("target_id", 0)
        user_id: int = raw.get("user_id", 0)
        self_id: int = raw.get("self_id", 0)
        group_id: int = raw.get("group_id", 0)

        # 冷却机制
        if not self.cooldown.allow(group_id, user_id):
            return

        # 过滤与自身无关的戳
        if target_id != self_id:
            # 跟戳机制
            if (
                group_id
                and user_id != self_id
                and random.random() < self.cfg.follow_poke_th
            ):
                await event.bot.group_poke(group_id=int(group_id), user_id=target_id)
            return

        # 随机选择一个响应函数
        handler = random.choices(
            population=self.response_handlers, weights=self.weights, k=1
        )[0]

        try:
            async for res in handler(event):
                yield res
        except Exception as e:
            logger.error(f"执行戳一戳响应失败: {e}", exc_info=True)

    # ========== 内部方法 ==========

    async def _send_cmd(self, event: AiocqhttpMessageEvent, command: str):
        """发送命令"""
        obj_msg = event.message_obj.message
        obj_msg.clear()
        obj_msg.extend([At(qq=event.get_self_id()), Plain(command)])
        event.is_at_or_wake_command = True
        event.message_str = command
        event.should_call_llm(True)
        event.set_extra("is_poke_event", True)
        self.context.get_event_queue().put_nowait(event)

    # ========== 响应函数 ==========

    async def poke_respond(self, event: AiocqhttpMessageEvent):
        """反戳"""
        await send_poke(
            event,
            target_ids=event.get_sender_id(),
            times=self.cfg.get_poke_times(),
        )
        event.stop_event()
        yield

    async def llm_respond(self, event: AiocqhttpMessageEvent):
        """调用llm回复"""
        template = self.cfg.llm_prompt_template
        if text := await self.llm.get_respond(event, template):
            yield event.plain_result(text)

    async def face_respond(self, event: AiocqhttpMessageEvent):
        """回复emoji(QQ表情)"""
        face_id = random.choice(self.cfg.face_ids)
        faces_chain: list[Face] = [Face(id=face_id)] * random.randint(1, 3)
        yield event.chain_result(faces_chain)  # type: ignore

    async def gallery_respond(self, event: AiocqhttpMessageEvent):
        """调用图库进行回复"""
        if files := list(self.cfg._gallery_path.iterdir()):
            selected_file = str(random.choice(files))
            yield event.image_result(selected_file)

    async def ban_respond(self, event: AiocqhttpMessageEvent):
        """禁言"""
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(event.get_sender_id()),
                duration=self.cfg.get_ban_time(),
            )
            prompt_template = self.cfg.ban_prompt_template

        except Exception:
            prompt_template = self.cfg.ban_fail_prompt_template
        finally:
            if text := await self.llm.get_respond(event, prompt_template):
                yield event.plain_result(text)

    async def meme_respond(self, event: AiocqhttpMessageEvent):
        """回复合成的meme"""
        await self._send_cmd(event, random.choice(self.cfg.meme_cmds))
        yield

    async def api_respond(self, event: AiocqhttpMessageEvent):
        "调用api"
        await self._send_cmd(event, random.choice(self.cfg.api_cmds))
        yield

    async def box_respond(self, event: AiocqhttpMessageEvent):
        """开盒"""
        await self._send_cmd(event, "盒")
        yield
