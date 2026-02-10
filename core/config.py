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

        # 戳一戳图库路径
        self._gallery_path = Path(self.gallery_path).resolve()
        self._gallery_path.mkdir(parents=True, exist_ok=True)

        # 初始化权重列表
        self.weight_list: list[int] = self.int_list(self.weight_str)

        # 表情ID列表
        self.face_ids: list[int] = self.int_list(self.face_ids_str) or [287]

        # meme命令列表
        self.meme_cmds: list[str] = self.str_list(self.meme_cmds_str)

        # api命令列表
        self.api_cmds: list[str] = self.str_list(self.api_cmds_str)

        # 戳一戳关键词
        self._poke_keywords: list[str] = self.str_list(self.poke_keywords)

        # 禁言时间
        self.min_ban_time, self.max_ban_time = map(int, self.ban_time.split("~"))

    def str_list(
        self,
        s: str,
        sep: tuple[str, ...] = (":", "：", ",", "，"),
    ) -> list[str]:
        pattern = "|".join(map(re.escape, sep))
        return [p.strip() for p in re.split(pattern, s) if p.strip()]

    def int_list(self, s: str) -> list[int]:
        try:
            return [int(x) for x in self.str_list(s)]
        except ValueError as e:
            raise ValueError(f"配置项包含非法整数: {e}")

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
