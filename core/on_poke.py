import copy
import random

from astrbot.api import logger
from astrbot.api.message_components import Face
from astrbot.core.message.components import At, Plain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context

from .llm import LLMService
from .config import PluginConfig
from .cooldown import Cooldown
from .model import PokeEvent
from .send_poke import PokeSender
from .model import PokeModel


class GetPokeHandler:
    def __init__(self, context: Context, config: PluginConfig, poke_sender: PokeSender):
        self.context = context
        self.cfg = config
        self.poke_sender = poke_sender
        self.llm = LLMService(context, self.cfg)
        self.cooldown = Cooldown(self.cfg)

        # 响应池：模块 → handler
        self.handlers = {
            PokeModel.ANTIPOKE: self.respond_poke,
            PokeModel.LLM: self.respond_llm,
            PokeModel.FACE: self.respond_face,
            PokeModel.meme: self.respond_meme,
            PokeModel.BAN: self.respond_ban,
            PokeModel.COMMAND: self.respond_cmd,
        }

        # 构建“可选模块池”
        self._modules, self._weights = self._build_response_pool()

    def _build_response_pool(self):
        pool = []
        for module, handler in self.handlers.items():
            weight = self.cfg.weight_of(module)
            if weight > 0:
                pool.append((module, weight))

        if not pool:
            logger.warning("所有响应模块权重均为 0，戳一戳功能已禁用")
            return (), ()

        modules, weights = zip(*pool)
        return modules, weights

    async def handle(self, event: AiocqhttpMessageEvent):
        """响应戳一戳事件"""
        if not self._modules:
            return

        if event.get_extra("is_poked"):
            return
        evt = PokeEvent.from_event(event)
        if not evt:
            return

        # 忽略自己发送的戳一戳
        if evt.is_self_send:
            return

        # 冷却机制
        if not self.cooldown.allow(evt.group_id, evt.user_id):
            return

        # 别人被戳则随机跟戳
        if not evt.is_self_poked and random.random() < self.cfg.follow_prob:
            await self.poke_sender.send(event, target_id=evt.target_id, times=1)
            return

        module = random.choices(self._modules, self._weights, k=1)[0]
        handler = self.handlers[module]

        try:
            async for msg in handler(event):
                if msg is not None:
                    yield msg
        except Exception as e:
            logger.error(f"执行戳一戳响应失败: {e}", exc_info=True)

    # ========== 响应函数 ==========

    async def respond_poke(self, event: AiocqhttpMessageEvent):
        """反戳"""
        await self.poke_sender.send(
            event,
            target_id=event.get_sender_id(),
            times=self.cfg.get_antipoke_times(),
        )
        event.stop_event()
        yield None

    async def respond_llm(self, event: AiocqhttpMessageEvent):
        """调用llm回复"""
        template = self.cfg.llm.template
        if text := await self.llm.get_respond(event, template):
            yield event.plain_result(text)

    async def respond_face(self, event: AiocqhttpMessageEvent):
        """回复emoji(QQ表情)"""
        face_id = self.cfg.get_face()
        copy_count = self.cfg.get_face_copy_count()
        faces_chain: list[Face] = [Face(id=face_id)] * copy_count
        yield event.chain_result(faces_chain)  # type: ignore

    async def respond_meme(self, event: AiocqhttpMessageEvent):
        """回复表情包"""
        img = self.cfg.get_image()
        yield event.image_result(img)

    async def respond_ban(self, event: AiocqhttpMessageEvent):
        """禁言"""
        cfg = self.cfg.ban
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(event.get_sender_id()),
                duration=self.cfg.get_ban_time(),
            )
            template = cfg.ban_template

        except Exception:
            template = cfg.ban_fail_template
        finally:
            if text := await self.llm.get_respond(event, template):
                yield event.plain_result(text)

    async def respond_cmd(self, event: AiocqhttpMessageEvent):
        """调用命令"""
        evt = copy.deepcopy(event)
        event.stop_event()

        cmd = self.cfg.get_command()

        obj_msg = evt.message_obj.message
        obj_msg.clear()
        obj_msg.extend([At(qq=evt.get_self_id()), Plain(cmd)])

        evt.is_at_or_wake_command = True
        evt.message_str = cmd
        evt.should_call_llm(True)
        evt.set_extra("is_poked", True)

        self.context.get_event_queue().put_nowait(evt)
        yield None
