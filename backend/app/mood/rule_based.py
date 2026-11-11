"""キーワード辞書による気分解析。外部通信なし・失敗しない。"""

from __future__ import annotations

from typing import Mapping

from ..domain.models import Mood, MoodReading

MAX_HITS_PER_MOOD = 3  # 同じ気分の語を何度書いても重みはここまで
MAX_MOODS_IN_SUMMARY = 3


class RuleBasedAnalyzer:
    def __init__(self, moods: Mapping[str, Mood]) -> None:
        self._moods = moods

    def read(self, text: str, count: int = 0) -> MoodReading:
        lowered = text.lower()
        weights: dict[str, float] = {}
        for mood in self._moods.values():
            hits = sum(1 for kw in mood.keywords if kw.lower() in lowered)
            if hits:
                weights[mood.key] = float(min(hits, MAX_HITS_PER_MOOD))

        if not weights:
            return MoodReading(summary="気分をうまく読み取れなかったので、作品世界から幅広く選びました。")

        top = sorted(weights, key=lambda k: weights[k], reverse=True)[:MAX_MOODS_IN_SUMMARY]
        labels = "」「".join(self._moods[k].label for k in top)
        return MoodReading(summary=f"「{labels}」の気分として受け取りました。", weights=weights)
