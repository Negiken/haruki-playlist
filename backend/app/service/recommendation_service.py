"""ユースケース「気分の文章 → おすすめ曲」。解析器と選曲ロジックをつなぐ唯一の場所。"""

from __future__ import annotations

import logging
import random
from collections import Counter

from ..catalog.repository import Catalog
from ..domain.models import MoodReading, Recommendation, RecommendationResult
from ..domain.recommender import MAX_PER_WORK, recommend
from ..mood.analyzer import AnalyzerError, MoodAnalyzer
from .limits import DailyBudget

log = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self,
        catalog: Catalog,
        fallback: MoodAnalyzer,
        primary: MoodAnalyzer | None = None,
        budget: DailyBudget | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._catalog = catalog
        self._primary = primary
        self._fallback = fallback
        self._budget = budget
        self._rng = rng or random.Random()

    @property
    def llm_enabled(self) -> bool:
        return self._primary is not None

    def recommend(self, text: str, count: int) -> RecommendationResult:
        engine, reading = self._read(text, count)
        chosen = self._validated_picks(reading, count)

        if len(chosen) < count:  # Claude の選曲が足りない／ルールベースの場合はここで選ぶ
            per_work = Counter(r.song.work.key for r in chosen)
            chosen += recommend(
                reading.weights,
                self._catalog.songs,
                self._catalog.moods,
                count - len(chosen),
                self._rng,
                exclude_ids=[r.song.id for r in chosen],
                work_counts=per_work,
            )
        return RecommendationResult(engine=engine, reading=reading, recommendations=tuple(chosen))

    def _read(self, text: str, count: int) -> tuple[str, MoodReading]:
        if self._primary is not None and (self._budget is None or self._budget.try_consume()):
            try:
                return "claude", self._primary.read(text, count)
            except AnalyzerError as e:
                log.warning("Claude 解析に失敗。ルールベースに切り替えます: %s", e)
        return "rules", self._fallback.read(text, count)

    def _validated_picks(self, reading: MoodReading, count: int) -> list[Recommendation]:
        """解析器が返した曲IDのうち、カタログに実在し重複・偏りのないものだけ採用する。"""
        chosen: list[Recommendation] = []
        seen: set[str] = set()
        per_work: Counter[str] = Counter()
        for pick in reading.picks:
            song = self._catalog.song(pick.song_id)
            if song is None or song.id in seen or per_work[song.work.key] >= MAX_PER_WORK:
                continue
            if len(chosen) >= count:
                break
            seen.add(song.id)
            per_work[song.work.key] += 1
            chosen.append(Recommendation(song, pick.reason or "この気分に寄り添う一曲。"))
        return chosen
