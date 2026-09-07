# -*- coding: utf-8 -*-
# 频率控制器：滑动窗口计数器，限制每小时 / 每天的转发次数（防风控）。

import time
from collections import deque


class RateLimiter:
    """基于滑动窗口的限频器。

    用两个时间戳队列分别记录最近 1 小时 / 24 小时内的转发时刻，
    每次转发前判断是否超限。
    """

    def __init__(self, max_per_hour=5, max_per_day=20):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self._hour = deque()
        self._day = deque()

    def _prune(self, dq, window):
        """清理队列中超过窗口期的旧记录。"""
        now = time.time()
        while dq and now - dq[0] > window:
            dq.popleft()

    def allow(self):
        """判断本次是否允许转发。允许则记录本次时间并返回 True。"""
        now = time.time()
        self._prune(self._hour, 3600)
        self._prune(self._day, 86400)

        if len(self._hour) >= self.max_per_hour:
            return False
        if len(self._day) >= self.max_per_day:
            return False

        self._hour.append(now)
        self._day.append(now)
        return True

    def hourly_used(self):
        """最近一小时已转发次数（用于日志提示）。"""
        self._prune(self._hour, 3600)
        return len(self._hour)
