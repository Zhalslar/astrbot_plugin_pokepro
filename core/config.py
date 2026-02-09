# config.py
from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
import random
import re
from typing import Any, get_type_hints

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context


class ConfigNode:
    """配置节点：dict → 强类型属性访问（极简版）"""

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        for key in self._schema():
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._schema():
            return self._data.get(key)
        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._schema():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)


# ============ 插件自定义配置 ==================


class PluginConfig(ConfigNode):
    # ====== 基础权重 / 概率 ======
    weight_str: str
    follow_poke_th: float

    # ====== 戳一戳行为控制 ======
    poke_max_times: int
    poke_interval: float
    cooldown_seconds: int

    # ====== LLM 提示 ======
    llm_prompt_template: str
    ban_prompt_template: str
    ban_fail_prompt_template: str

    # ====== 禁言相关 ======
    ban_time: str

    # ====== 回复资源 ======
    face_ids_str: str
    meme_cmds_str: str
    api_cmds_str: str
    gallery_path: str

    # ====== 关键词 ======
    poke_keywords: str

    def __init__(self, cfg: AstrBotConfig, context: Context):
        super().__init__(cfg)
        self.context = context
        # 初始化权重列表
        self.weight_list: list[int] = self.string_to_list(self.weight_str, "int")  # type: ignore

        # 表情ID列表
        self.face_ids: list[int] = self.string_to_list(self.face_ids_str, "int") or [
            287
        ]  # type: ignore

        # 戳一戳图库路径
        self._gallery_path = Path(self.gallery_path).resolve()
        self._gallery_path.mkdir(parents=True, exist_ok=True)

        # meme命令列表
        self.meme_cmds: list[str] = self.string_to_list(self.meme_cmds_str, "str")  # type: ignore

        # api命令列表
        self.api_cmds: list[str] = self.string_to_list(self.api_cmds_str, "str")  # type: ignore

        # 戳一戳关键词
        self._poke_keywords: list[str] = self.string_to_list(self.poke_keywords, "str")  # type: ignore

        # 禁言时间
        self.min_ban_time, self.max_ban_time = map(int, self.ban_time.split("~"))

    def hit_poke_keywords(self, text: str) -> bool:
        """判断是否命中戳一戳关键词"""
        for keyword in self._poke_keywords:
            if keyword in text:
                return True
        return False

    def get_poke_times(self, times: int | None = None) -> int:
        """获取戳一戳次数"""
        if times:
            return min(self.poke_max_times, times)
        return random.randint(1, self.poke_max_times)

    def get_ban_time(self) -> int:
        """获取禁言时间"""
        return random.randint(self.min_ban_time, self.max_ban_time)

    @staticmethod
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
