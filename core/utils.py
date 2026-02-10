import asyncio
import random
from aiocqhttp import CQHttp
from astrbot.api import logger
from astrbot.core.message.components import At, Plain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.context import Context


async def get_nickname(client: CQHttp, group_id: int | str, user_id: int | str) -> str:
    """获取指定群友的群昵称或 Q 名，群接口失败/空结果自动降级到陌生人资料"""
    user_id = int(user_id)

    info = {}

    # 在群里就先试群资料，任何异常或空结果都跳过
    if str(group_id).isdigit():
        try:
            info = (
                await client.get_group_member_info(
                    group_id=int(group_id), user_id=user_id
                )
                or {}
            )
        except Exception:
            pass

    # 群资料没拿到就降级到陌生人资料
    if not info:
        try:
            info = await client.get_stranger_info(user_id=user_id) or {}
        except Exception:
            pass

    # 依次取群名片、QQ 昵称、通用 nick，兜底数字 UID
    return info.get("card") or info.get("nickname") or info.get("nick") or str(user_id)


def get_ats(
    event: AiocqhttpMessageEvent,
    noself: bool = False,
    block_ids: list[str] | None = None,
    skip_first_seg: bool = True,
):
    """
    获取被at者们的id列表(@增强版)
    Args:
        event: 消息事件对象
        noself: 是否排除自己
        block_ids: 要排除的id列表
        skip_first_seg: 是否跳过第一个消息段（默认为True）
    """
    segs = event.get_messages()
    segs = segs[1:] if skip_first_seg else segs
    ats = {str(seg.qq) for seg in segs if isinstance(seg, At)}
    ats.update(
        arg[1:]
        for arg in event.message_str.split()
        if arg.startswith("@") and arg[1:].isdigit()
    )
    if noself:
        ats.discard(event.get_self_id())
    if block_ids:
        ats.difference_update(block_ids)
    return list(ats)


async def get_member_ids(event: AiocqhttpMessageEvent, num: int = 200) -> list[int]:
    """获取群成员ID列表"""
    try:
        members_data = await event.bot.get_group_member_list(
            group_id=int(event.get_group_id())
        )
        user_ids = [member.get("user_id", "") for member in members_data]
        return random.sample(user_ids, min(num, len(user_ids)))
    except Exception as e:
        logger.error(f"获取群成员信息失败：{e}")
        return []


async def send_poke(
    event: AiocqhttpMessageEvent,
    target_ids: list | str,
    *,
    times: int = 1,
    interval: int = 0,
):
    """发送戳一戳"""
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
            await event.bot.group_poke(group_id=int(group_id), user_id=tid)
        else:
            await event.bot.friend_poke(user_id=tid)

    try:
        for tid in target_ids:
            for _ in range(times):
                await poke_func(tid)
                await asyncio.sleep(interval)
    except Exception as e:
        logger.error(f"发送戳一戳失败：{e}")

def send_cmd(context: Context, event: AiocqhttpMessageEvent, command: str):
    """发送命令"""
    obj_msg = event.message_obj.message
    obj_msg.clear()
    obj_msg.extend([At(qq=event.get_self_id()), Plain(command)])
    event.is_at_or_wake_command = True
    event.message_str = command
    event.should_call_llm(True)
    event.set_extra("is_poked", True)
    context.get_event_queue().put_nowait(event)
