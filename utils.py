
import re

from aiocqhttp import CQHttp


def string_to_list(
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




