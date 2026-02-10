# config.py
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
import random
from types import MappingProxyType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_path

from .model import PokeModel


class ConfigNode:
    """
    配置节点, 把 dict 变成强类型对象。

    规则：
    - schema 来自子类类型注解
    - 声明字段：读写，写回底层 dict
    - 未声明字段和下划线字段：仅挂载属性，不写回
    - 支持 ConfigNode 多层嵌套（lazy + cache）
    """

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}
    _FIELDS_CACHE: dict[type, set[str]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    @classmethod
    def _fields(cls) -> set[str]:
        return cls._FIELDS_CACHE.setdefault(
            cls,
            {k for k in cls._schema() if not k.startswith("_")},
        )

    @staticmethod
    def _is_optional(tp: type) -> bool:
        if get_origin(tp) in (Union, UnionType):
            return type(None) in get_args(tp)
        return False

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_children", {})
        for key, tp in self._schema().items():
            if key.startswith("_"):
                continue
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            if self._is_optional(tp):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._fields():
            value = self._data.get(key)
            tp = self._schema().get(key)

            if isinstance(tp, type) and issubclass(tp, ConfigNode):
                children: dict[str, ConfigNode] = self.__dict__["_children"]
                if key not in children:
                    if not isinstance(value, MutableMapping):
                        raise TypeError(
                            f"[config:{self.__class__.__name__}] "
                            f"字段 {key} 期望 dict，实际是 {type(value).__name__}"
                        )
                    children[key] = tp(value)
                return children[key]

            return value

        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._fields():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)

    def raw_data(self) -> Mapping[str, Any]:
        """
        底层配置 dict 的只读视图
        """
        return MappingProxyType(self._data)

    def save_config(self) -> None:
        """
        保存配置到磁盘（仅允许在根节点调用）
        """
        if not isinstance(self._data, AstrBotConfig):
            raise RuntimeError(
                f"{self.__class__.__name__}.save_config() 只能在根配置节点上调用"
            )
        self._data.save_config()


# ============ 插件自定义配置 ==================


class AntiPokeConfig(ConfigNode):
    weight: int
    max_times: int


class LLMConfig(ConfigNode):
    weight: int
    template: str


class FaceConfig(ConfigNode):
    weight: int
    pool: list[int]
    max_copy_count: int


class MemeConfig(ConfigNode):
    weight: int
    pool: list[str]


class BanConfig(ConfigNode):
    weight: int
    duration: int
    delta: int
    ban_template: str
    ban_fail_template: str


class CommandConfig(ConfigNode):
    weight: int
    pool: list[str]

class SchedulerConfig(ConfigNode):
    enabled: bool
    cron: str
    target: list[str]
    times: int


class PluginConfig(ConfigNode):
    on_poke: bool
    poke_cd: int
    follow_prob: float

    antipoke: AntiPokeConfig
    llm: LLMConfig
    face: FaceConfig
    meme: MemeConfig
    ban: BanConfig
    command: CommandConfig

    poke_max_times: int
    poke_interval: float
    poke_keywords: list[str]

    scheduler: SchedulerConfig

    _plugin_name = "astrbot_plugin_pokepro"

    def __init__(self, cfg: AstrBotConfig, context: Context):
        super().__init__(cfg)
        self.context = context
        self.target_list = self._parse_target()

        self.data_dir = StarTools.get_data_dir(self._plugin_name)
        self.plugin_dir = Path(get_astrbot_plugin_path()) / self._plugin_name
        self.logo_path = self.plugin_dir / "logo.png"
        self.file_pool_dir = self.data_dir / "files" / "meme" / "pool"
        self.file_pool_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_non_empty_pools()
        self.save_config()

    def _parse_target(self) -> list[tuple[str, str]]:
        target_list = []
        for arg in self.scheduler.target:
            try:
                group, qq = arg.split(":")
                target_list.append((group, qq))
            except ValueError:
                pass
        return target_list

    def _ensure_non_empty_pools(self) -> None:
        if not self.face.pool:
            self.face.pool.append(1)
            logger.warning("QQ表情池为空，已添加默认值：1")

        if not self.command.pool:
            self.command.pool.append("盒")
            logger.warning("命令池为空，已添加默认值：盒")

        if not self.meme.pool:
            target = self.file_pool_dir / self.logo_path.name
            self.meme.pool.append("files/meme/pool/logo.png")
            if not target.exists():
                try:
                    target.write_bytes(self.logo_path.read_bytes())
                    logger.warning(f"表情包池为空，已复制 logo 到默认池：{target}")
                except Exception as e:
                    logger.error(
                        f"复制默认表情包失败：{self.logo_path} -> {target}, {e}"
                    )

    # ================= 业务辅助方法 =================

    def hit_poke_keywords(self, text: str) -> bool:
        """判断是否命中关键词"""
        return any(k in text for k in self.poke_keywords)

    def get_antipoke_times(self) -> int:
        """获取反戳次数"""
        return random.randint(1, self.antipoke.max_times)

    def get_face_copy_count(self):
        """获取QQ表情复制次数"""
        return random.randint(1, self.face.max_copy_count)

    def get_ban_time(self) -> int:
        """获取禁言时间"""
        delta = random.randint(-self.ban.delta, self.ban.delta)
        return max(0, self.ban.duration + delta)

    def get_command(self):
        """获取命令"""
        return random.choice(self.command.pool)

    def get_face(self) -> int:
        """获取表情包"""
        return random.choice(self.face.pool)

    def get_image(self) -> str:
        """获取图片"""
        rel_path = Path(random.choice(self.meme.pool))
        abs_path = self.data_dir / rel_path
        return str(abs_path.resolve())

    def weight_of(self, module: PokeModel) -> int:
        return {
            PokeModel.ANTIPOKE: self.antipoke.weight,
            PokeModel.LLM: self.llm.weight,
            PokeModel.FACE: self.face.weight,
            PokeModel.meme: self.meme.weight,
            PokeModel.BAN: self.ban.weight,
            PokeModel.COMMAND: self.command.weight,
        }[module]
