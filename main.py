import asyncio
import json
import random
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import At, Face, Image, Plain, Poke
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.config.default import VERSION
from astrbot.core.db.po import Persona
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.utils.version_comparator import VersionComparator


@register("astrbot_plugin_pokepro", "Zhalslar", "...", "...")
class PokeproPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config

        # 检查版本
        if not VersionComparator.compare_version(VERSION, "4.5.7") >= 0:
            raise Exception("AstrBot 版本过低, 请升级至 4.5.7 或更高版本")

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

        # 初始化权重列表
        weight_str = config.get("weight_str", "")
        weight_list: list[int] = self._string_to_list(weight_str, "int")  # type: ignore
        self.weights: list[int] = weight_list + [1] * (
            len(self.response_handlers) - len(weight_list)
        )

        # 记录每个 user_id 的最后触发时间
        self.last_trigger_time = {}

        # 表情ID列表
        self.face_ids: list[int] = self._string_to_list(config["face_ids_str"], "int")  # type: ignore

        # 戳一戳图库路径
        self.gallery_path: Path = Path(config.get("gallery_path", ""))
        self.gallery_path.mkdir(parents=True, exist_ok=True)

        # meme命令列表
        self.meme_cmds: list[str] = self._string_to_list(config["meme_cmds_str"], "str")  # type: ignore

        # api命令列表
        self.api_cmds: list[str] = self._string_to_list(config["api_cmds_str"], "str")  # type: ignore

        # 戳一戳关键词
        self.poke_keywords: list[str] = self._string_to_list(
            config["poke_keywords"], "str"
        )  # type: ignore

    def _string_to_list(
        self,
        input_str: str,
        return_type: str = "str",
        sep: str | list[str] = [":", "：", ",", "，"],
    ) -> list[str | int]:
        """
        将字符串转换为列表，支持自定义一个或多个分隔符和返回类型。

        参数：
            input_str (str): 输入字符串。
            return_type (str): 返回类型，'str' 或 'int'。
            sep (Union[str, List[str]]): 一个或多个分隔符，默认为 [":", "；", ",", "，"]。
        返回：
            List[Union[str, int]]
        """
        # 如果sep是列表，则创建一个包含所有分隔符的正则表达式模式
        if isinstance(sep, list):
            pattern = "|".join(map(re.escape, sep))
        else:
            # 如果sep是单个字符，则直接使用
            pattern = re.escape(sep)

        parts = [p.strip() for p in re.split(pattern, input_str) if p.strip()]

        if return_type == "int":
            try:
                return [int(p) for p in parts]
            except ValueError as e:
                raise ValueError(f"转换失败 - 无效的整数: {e}")
        elif return_type == "str":
            return parts
        else:
            raise ValueError("return_type 必须是 'str' 或 'int'")

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

    @staticmethod
    async def get_nickname(event: AiocqhttpMessageEvent, user_id) -> str:
        """获取指定群友的群昵称或Q名"""
        client = event.bot
        group_id = event.get_group_id()
        if group_id:
            member_info = await client.get_group_member_info(
                group_id=int(group_id), user_id=int(user_id)
            )
            return member_info.get("card") or member_info.get("nickname")
        else:
            stranger_info = await client.get_stranger_info(user_id=int(user_id))
            return stranger_info.get("nickname")

    async def _get_llm_respond(
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
                persona_id=persona_id
            )
            system_prompt = persona.system_prompt
        except ValueError:
            # 回退到默认人格
            personality: Personality = await self.context.persona_manager.get_default_persona_v3(
                umo=umo
            )
            system_prompt = personality["prompt"]

        # 获取提示词
        username = await self.get_nickname(event, event.get_sender_id())
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_poke(self, event: AiocqhttpMessageEvent):
        """监听并响应戳一戳事件"""
        if event.get_extra("is_poke_event"):
            return
        raw_message = getattr(event.message_obj, "raw_message", None)

        if (
            not raw_message
            or not event.message_obj.message
            or not isinstance(event.message_obj.message[0], Poke)
        ):
            return

        target_id: int = raw_message.get("target_id", 0)
        user_id: int = raw_message.get("user_id", 0)
        self_id: int = raw_message.get("self_id", 0)
        group_id: int = raw_message.get("group_id", 0)

        # 冷却机制
        current_time = time.monotonic()
        last_time = self.last_trigger_time.get(user_id, 0)
        if current_time - last_time < self.conf["cooldown_seconds"]:
            return
        self.last_trigger_time[user_id] = current_time

        # 过滤与自身无关的戳
        if target_id != self_id:
            # 跟戳机制
            if (
                group_id
                and user_id != self_id
                and random.random() < self.conf["follow_poke_th"]
            ):
                await event.bot.group_poke(group_id=int(group_id), user_id=target_id)
            return

        # 随机选择一个响应函数
        selected_handler = random.choices(
            population=self.response_handlers, weights=self.weights, k=1
        )[0]

        try:
            await selected_handler(event)
        except Exception as e:
            logger.error(f"执行戳一戳响应失败: {e}", exc_info=True)

    # ========== 响应函数 ==========
    async def poke_respond(self, event: AiocqhttpMessageEvent):
        """反戳"""
        await self._poke(
            event=event,
            target_ids=event.get_sender_id(),
            times=random.randint(1, self.conf["poke_max_times"]),
        )
        event.stop_event()

    async def llm_respond(self, event: AiocqhttpMessageEvent):
        """调用llm回复"""
        if text := await self._get_llm_respond(event, self.conf["llm_prompt_template"]):
            await event.send(event.plain_result(text))
            event.stop_event()

    async def face_respond(self, event: AiocqhttpMessageEvent):
        """回复emoji(QQ表情)"""
        face_id = random.choice(self.face_ids) if self.face_ids else 287
        faces_chain: list[Face] = [Face(id=face_id)] * random.randint(1, 3)
        await event.send(MessageChain(chain=faces_chain))  # type: ignore
        event.stop_event()

    async def gallery_respond(self, event: AiocqhttpMessageEvent):
        """调用图库进行回复"""
        if files := list(self.gallery_path.iterdir()):
            selected_file = str(random.choice(files))
            await event.send(MessageChain(chain=[Image(selected_file)]))  # type: ignore
            event.stop_event()

    async def ban_respond(self, event: AiocqhttpMessageEvent):
        """禁言"""
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(event.get_sender_id()),
                duration=random.randint(*map(int, self.conf["ban_time"].split("~"))),
            )
            prompt_template = self.conf["ban_prompt_template"]

        except Exception:
            prompt_template = self.conf["ban_fail_prompt_template"]
        finally:
            text = await self._get_llm_respond(event, prompt_template)
            await event.send(MessageChain(chain=[Plain(text)]))  # type: ignore
            event.stop_event()

    async def meme_respond(self, event: AiocqhttpMessageEvent):
        """回复合成的meme"""
        await self._send_cmd(event, random.choice(self.meme_cmds))

    async def api_respond(self, event: AiocqhttpMessageEvent):
        "调用api"
        await self._send_cmd(event, random.choice(self.api_cmds))

    async def box_respond(self, event: AiocqhttpMessageEvent):
        """开盒"""
        await self._send_cmd(event, "盒")

    @filter.command("戳", alias={"戳我", "戳全体成员"})
    async def poke_handle(self, event: AiocqhttpMessageEvent):
        """戳@某人/我/全体成员"""
        target_ids = [
            str(seg.qq)
            for seg in event.get_messages()
            if isinstance(seg, At) and str(seg.qq) != event.get_self_id()
        ]

        parsed_msg = event.message_str.split()
        times = int(parsed_msg[-1]) if parsed_msg[-1].isdigit() else 1
        if not event.is_admin():
            times = min(self.conf["poke_max_times"], times)

        if "我" in event.message_str:
            target_ids.append(event.get_sender_id())

        if "全体成员" in event.message_str and event.is_admin():
            try:
                members_data = await event.bot.get_group_member_list(
                    group_id=int(event.get_group_id())
                )
                user_ids = [member.get("user_id", "") for member in members_data]
                # 由于每天戳一戳上限为200个，故只随机取200个
                target_ids = random.sample(user_ids, min(200, len(user_ids)))
            except Exception as e:
                yield event.plain_result(f"获取群成员信息失败：{e}")
                return

        if not target_ids:
            result: dict = await event.bot.get_group_msg_history(
                group_id=int(event.get_group_id())
            )
            target_ids = [msg["sender"]["user_id"] for msg in result["messages"]]

        if not target_ids:
            return

        await self._poke(event, target_ids, times)
        event.stop_event()

    async def _poke(
        self,
        event: AiocqhttpMessageEvent,
        target_ids: list | str,
        times: int = 1,
    ):
        """执行戳一戳"""
        client = event.bot
        group_id = event.get_group_id()
        self_id = int(event.get_self_id())
        if isinstance(target_ids, str | int):
            target_ids = [target_ids]
        target_ids = list(
            dict.fromkeys(  # 保留顺序去重
                int(tid) for tid in target_ids if int(tid) != self_id
            )
        )

        async def poke_func(tid: int):
            if group_id:
                await client.group_poke(group_id=int(group_id), user_id=tid)
            else:
                await client.friend_poke(user_id=tid)

        try:
            for tid in target_ids:
                for _ in range(times):
                    await poke_func(tid)
                    await asyncio.sleep(self.conf["poke_interval"])
        except Exception as e:
            logger.error(f"执行戳一戳失败：{e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def keyword_poke(self, event: AiocqhttpMessageEvent):
        if event.is_at_or_wake_command:
            for keyword in self.poke_keywords:
                if keyword in event.message_str:
                    await self._poke(event, event.get_sender_id())
                    break
