# core/cooldown.py
from __future__ import annotations

import time
from typing import Dict, Tuple

from .config import PluginConfig


class Cooldown:
    """按 (group_id, user_id) 维度的冷却器"""

    def __init__(self, config: PluginConfig):
        self.cfg = config
        self.cooldown_seconds: float = config.cooldown_seconds
        self._last_trigger: Dict[Tuple[int, int], float] = {}
        self._clock = time.monotonic

    def allow(self, group_id: int | None, user_id: int) -> bool:
        """
        判断是否允许触发
        - group_id: None / 0 表示私聊
        - user_id: 触发用户
        """
        gid = int(group_id or 0)
        uid = int(user_id)
        key = (gid, uid)

        now = self._clock()
        last = self._last_trigger.get(key)

        if last is not None and now - last < self.cooldown_seconds:
            return False

        self._last_trigger[key] = now
        return True

    def remaining(self, group_id: int | None, user_id: int) -> float:
        """返回剩余冷却时间（秒），<=0 表示已冷却"""
        gid = int(group_id or 0)
        uid = int(user_id)
        key = (gid, uid)

        last = self._last_trigger.get(key)
        if last is None:
            return 0.0

        left = self.cooldown_seconds - (self._clock() - last)
        return max(left, 0.0)

    def reset(self, group_id: int | None, user_id: int) -> None:
        """手动清除某人的冷却"""
        gid = int(group_id or 0)
        uid = int(user_id)
        self._last_trigger.pop((gid, uid), None)

    def clear(self) -> None:
        """清空所有冷却（热重载配置时可用）"""
        self._last_trigger.clear()
