"""ドメインモデル。外部ライブラリ・I/O に依存しない。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mood:
    """気分タグ。key が語彙、keywords はルールベース判定用。"""

    key: str
    label: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    year: int
    kind: str  # 長編 / 短編集
    source_url: str
    cover_url: str | None = None  # 書影（外部サイトの画像URL）


@dataclass(frozen=True)
class Song:
    id: str
    title: str
    title_original: str
    artist: str
    genre: str  # jazz / pop / classical / other
    work: Work
    scene: str  # 作中での登場場面（要約）
    moods: tuple[str, ...]
    source_url: str  # この情報の出典ページ
    story: str | None = None  # 短編集の場合の収録短編名
    verification: str = "sourced"  # sourced / partial（曲名や場面が出典で未確認）
    artwork_url: str | None = None  # ジャケット画像（外部サイトの画像URL）
    apple_url: str | None = None  # ジャケットの提供元である Apple Music の曲ページ


@dataclass(frozen=True)
class Pick:
    """解析器が直接選んだ曲（Claude のみが返す）。"""

    song_id: str
    reason: str


@dataclass(frozen=True)
class MoodReading:
    """入力文から読み取った気分。"""

    summary: str
    weights: dict[str, float] = field(default_factory=dict)  # mood key -> 重み
    picks: tuple[Pick, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    song: Song
    reason: str


@dataclass(frozen=True)
class RecommendationResult:
    engine: str  # claude / rules
    reading: MoodReading
    recommendations: tuple[Recommendation, ...]
