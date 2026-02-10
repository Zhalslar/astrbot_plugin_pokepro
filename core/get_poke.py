import random

from astrbot.api import logger
from astrbot.api.message_components import Face
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context

from .llm import LLMService
from .config import PluginConfig
from .cooldown import Cooldown
from .utils import send_poke, send_cmd

# 示例原始数据
# raw = {
#     "time": 1770684953,
#     "self_id": 1959676873,
#     "post_type": "notice",
#     "notice_type": "notify",
#     "sub_type": "poke",
#     "target_id": 1959676873,
#     "user_id": 2936169201,
#     "group_id": 952212291,
#     "raw_info": [
#         {"col": "1", "nm": "", "type": "qq", "uid": "u_QmVcCfvoEUKZv6rb2WM7Lw"},
#         {
#             "jp": "https://zb.vip.qq.com/v2/pages/nudgeMall?_wv=2&actionId=0&effectId=5",
#             "src": "http://tianquan.gtimg.cn/nudgeeffect/item/5/client.gif",
#             "type": "img",
#         },
#         {
#             "col": "1",
#             "nm": "",
#             "tp": "0",
#             "type": "qq",
#             "uid": "u_4Twr4XaJJ8CPkZI5hKOPsw",
#         },
#         {"txt": "的服务器", "type": "nor"},
#     ],
# }

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
        if event.get_extra("is_poked"):
            return
        raw: dict = getattr(event.message_obj, "raw_message", {})
        if not raw or not raw.get("sub_type") == "poke":
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
            async for msg in handler(event):
                if msg is not None:
                    yield msg
        except Exception as e:
            logger.error(f"执行戳一戳响应失败: {e}", exc_info=True)

    # ========== 响应函数 ==========

    async def poke_respond(self, event: AiocqhttpMessageEvent):
        """反戳"""
        await send_poke(
            event,
            target_ids=event.get_sender_id(),
            times=self.cfg.get_poke_times(),
        )
        event.stop_event()
        yield None

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
        send_cmd(self.context, event, random.choice(self.cfg.meme_cmds))
        yield None

    async def api_respond(self, event: AiocqhttpMessageEvent):
        "调用api"
        send_cmd(self.context, event, random.choice(self.cfg.api_cmds))
        yield None

    async def box_respond(self, event: AiocqhttpMessageEvent):
        """开盒"""
        send_cmd(self.context, event, "盒")
        yield None
