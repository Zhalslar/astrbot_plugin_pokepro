# core/cooldown.py
from __future__ import annotations

import time

from .config import PluginConfig


class Cooldown:
    def __init__(self, config: PluginConfig):
        self.cfg = config
        self.cd: float = config.poke_cd or 0
        self.group_cd: float = config.group_poke_cd or 0
        self._last_trigger: dict[tuple[int, int], float] = {}
        self._last_group_trigger: dict[int, float] = {}
        self._clock = time.monotonic

    def allow(self, group_id: int | None, user_id: int) -> bool:
        gid = int(group_id or 0)
        uid = int(user_id)
        key = (gid, uid)

        now = self._clock()
        last = self._last_trigger.get(key)

        if self.cd > 0 and last is not None and now - last < self.cd:
            return False

        group_last = self._last_group_trigger.get(gid)
        if (
            gid
            and self.group_cd > 0
            and group_last is not None
            and now - group_last < self.group_cd
        ):
            return False

        self._last_trigger[key] = now
        if gid and self.group_cd > 0:
            self._last_group_trigger[gid] = now
        return True

    def remaining(self, group_id: int | None, user_id: int) -> float:
        gid = int(group_id or 0)
        uid = int(user_id)
        key = (gid, uid)
        now = self._clock()

        last = self._last_trigger.get(key)
        user_left = 0.0
        if self.cd > 0 and last is not None:
            user_left = self.cd - (now - last)

        group_left = 0.0
        group_last = self._last_group_trigger.get(gid)
        if gid and self.group_cd > 0 and group_last is not None:
            group_left = self.group_cd - (now - group_last)

        return max(user_left, group_left, 0.0)

    def reset(self, group_id: int | None, user_id: int) -> None:
        gid = int(group_id or 0)
        uid = int(user_id)
        self._last_trigger.pop((gid, uid), None)

    def clear(self) -> None:
        self._last_trigger.clear()
        self._last_group_trigger.clear()
