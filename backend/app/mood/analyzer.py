"""気分解析の抽象。実装は rule_based（常に使える）と claude（任意）。"""

from __future__ import annotations

from typing import Protocol

from ..domain.models import MoodReading


class AnalyzerError(Exception):
    """解析に失敗した。呼び出し側はフォールバックに切り替える。"""


class MoodAnalyzer(Protocol):
    def read(self, text: str, count: int) -> MoodReading:
        """入力文から気分を読み取る。失敗時は AnalyzerError を送出する。"""
        ...
