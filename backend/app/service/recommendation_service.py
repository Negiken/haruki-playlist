"""ユースケース「気分の文章 → おすすめ曲」。解析器と選曲ロジックをつなぐ唯一の場所。"""

from __future__ import annotations

import logging
import random
from collections import Counter
from typing import Iterable

from ..catalog.repository import Catalog
from ..domain.models import MoodReading, Recommendation, RecommendationResult
from ..domain.recommender import MAX_PER_WORK, recommend
from ..mood.analyzer import AnalyzerError, MoodAnalyzer
from .limits import DailyBudget

log = logging.getLogger(__name__)

POOL_SIZE = 5  # 抽選のために集める候補の数（求められた曲数がこれより多ければ、その数）


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

    def recommend(self, text: str, count: int, exclude: Iterable[str] = ()) -> RecommendationResult:
        """気分に合う候補を多めに集め、その中から count 曲を抽選する。

        解析器は同じ気分にいつも同じ「いちばん合う曲」を返すので、候補から抽選しないと
        同じ曲ばかりになる。exclude は閲覧者が最近聴いた曲で、候補から外す。
        """
        pool_size = max(count, POOL_SIZE)
        excluded = set(exclude)
        engine, reading = self._read(text, pool_size)
        pool = self._validated_picks(reading, excluded)[:pool_size]

        # Claude の選曲が足りなければ不足分だけ補う。1曲も無い（ルールベース等）なら候補ごと作る
        target = count if pool else pool_size
        if len(pool) < target:
            pool += recommend(
                reading.weights,
                self._catalog.songs,
                self._catalog.moods,
                target - len(pool),
                self._rng,
                exclude_ids=excluded | {r.song.id for r in pool},
                work_counts=Counter(r.song.work.key for r in pool),
            )

        if len(pool) > count:  # 抽選。選ばれた曲どうしの順番は保つ
            keep = sorted(self._rng.sample(range(len(pool)), count))
            pool = [pool[i] for i in keep]
        return RecommendationResult(engine=engine, reading=reading, recommendations=tuple(pool))

    def _read(self, text: str, count: int) -> tuple[str, MoodReading]:
        if self._primary is not None and (self._budget is None or self._budget.try_consume()):
            try:
                return "claude", self._primary.read(text, count)
            except AnalyzerError as e:
                log.warning("Claude 解析に失敗。ルールベースに切り替えます: %s", e)
        return "rules", self._fallback.read(text, count)

    def _validated_picks(self, reading: MoodReading, excluded: set[str]) -> list[Recommendation]:
        """解析器が返した曲IDのうち、カタログに実在し、除外・重複・偏りのないものだけ採用する。"""
        chosen: list[Recommendation] = []
        seen: set[str] = set(excluded)
        per_work: Counter[str] = Counter()
        for pick in reading.picks:
            song = self._catalog.song(pick.song_id)
            if song is None or song.id in seen or per_work[song.work.key] >= MAX_PER_WORK:
                continue
            seen.add(song.id)
            per_work[song.work.key] += 1
            chosen.append(Recommendation(song, pick.reason or "この気分に寄り添う一曲。"))
        return chosen
