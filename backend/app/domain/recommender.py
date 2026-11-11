"""気分の重みから曲を選ぶ。純粋関数のみ（乱数は引数で受け取る）。"""

from __future__ import annotations

import random
from collections import Counter
from typing import Iterable, Mapping, Sequence

from .models import Mood, Recommendation, Song

MAX_PER_WORK = 2  # 同じ作品ばかり並ばないようにする
JITTER = 0.35  # 同じ入力でも毎回少し違う並びにする


def score(song: Song, weights: Mapping[str, float]) -> float:
    return sum(weights.get(m, 0.0) for m in song.moods)


def recommend(
    weights: Mapping[str, float],
    songs: Sequence[Song],
    moods: Mapping[str, Mood],
    count: int,
    rng: random.Random,
    exclude_ids: Iterable[str] = (),
    work_counts: Mapping[str, int] | None = None,
) -> list[Recommendation]:
    """重みに合う曲を count 件まで返す。重みが空なら幅広くランダムに選ぶ。"""
    excluded = set(exclude_ids)
    per_work: Counter[str] = Counter(work_counts or {})

    ranked = sorted(
        (s for s in songs if s.id not in excluded),
        key=lambda s: score(s, weights) + rng.random() * JITTER,
        reverse=True,
    )

    chosen: list[Recommendation] = []
    for song in ranked:
        if len(chosen) >= count:
            break
        if per_work[song.work.key] >= MAX_PER_WORK:
            continue
        per_work[song.work.key] += 1
        chosen.append(Recommendation(song, build_reason(song, weights, moods)))
    return chosen


def build_reason(song: Song, weights: Mapping[str, float], moods: Mapping[str, Mood]) -> str:
    matched = sorted(
        (m for m in song.moods if weights.get(m, 0.0) > 0),
        key=lambda m: weights[m],
        reverse=True,
    )
    if not matched:
        return "気分を限定せず、作品世界から一曲。"
    labels = "」「".join(moods[m].label for m in matched if m in moods)
    return f"「{labels}」の気分に重なる一曲。"
