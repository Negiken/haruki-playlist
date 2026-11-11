"""公開URLを守るための2つの上限。どちらもプロセス内メモリで持つ（1台・1ワーカー前提）。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date
from typing import Callable


class DailyBudget:
    """1日あたりの Claude 呼び出し回数の上限。超えた分はルールベースに回す。"""

    def __init__(self, limit: int, today: Callable[[], date] = date.today) -> None:
        self._limit = limit
        self._today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def try_consume(self) -> bool:
        with self._lock:
            now = self._today()
            if now != self._day:
                self._day, self._used = now, 0
            if self._used >= self._limit:
                return False
            self._used += 1
            return True


class RateLimiter:
    """IPごとのスライディングウィンドウ制限。"""

    def __init__(self, max_requests: int, window_sec: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._max = max_requests
        self._window = window_sec
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._max:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:  # 期限切れのキーを掃除
                stale = [k for k, v in self._hits.items() if now - v[-1] >= self._window]
                for k in stale:
                    del self._hits[k]
            return True
