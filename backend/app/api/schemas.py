"""HTTP の入出力の形。ドメインモデルからの変換もここで行う。"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, field_validator

from ..catalog.repository import Catalog
from ..domain.models import Recommendation, RecommendationResult

MAX_TEXT_CHARS = 500
DEFAULT_COUNT = 1  # 画面は一度に一曲だけ出す
MAX_COUNT = 8
MAX_EXCLUDE = 30


class RecommendationRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    count: int = Field(default=DEFAULT_COUNT, ge=1, le=MAX_COUNT)
    # 最近出た曲のID。続けて同じ曲が出ないよう、画面が覚えていて送ってくる
    exclude: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=MAX_EXCLUDE)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("気分を入力してください")
        return v


class WorkOut(BaseModel):
    key: str
    title: str
    year: int
    kind: str
    cover_url: str | None


class SongOut(BaseModel):
    id: str
    title: str
    title_original: str
    artist: str
    genre: str
    work: WorkOut
    story: str | None
    scene: str
    reason: str
    source_url: str
    verified: bool
    listen_url: str
    artwork_url: str | None
    apple_url: str | None


class MoodTagOut(BaseModel):
    key: str
    label: str


class MoodOut(BaseModel):
    summary: str
    tags: list[MoodTagOut]


class RecommendationResponse(BaseModel):
    engine: str
    mood: MoodOut
    songs: list[SongOut]


class WorkSummary(WorkOut):
    song_count: int
    source_url: str


class HealthResponse(BaseModel):
    status: str
    version: str
    songs: int
    llm_enabled: bool


def to_response(result: RecommendationResult, catalog: Catalog) -> RecommendationResponse:
    weights = result.reading.weights
    tags = [
        MoodTagOut(key=k, label=catalog.moods[k].label)
        for k in sorted(weights, key=lambda k: weights[k], reverse=True)[:3]
        if k in catalog.moods
    ]
    return RecommendationResponse(
        engine=result.engine,
        mood=MoodOut(summary=result.reading.summary, tags=tags),
        songs=[_song_out(r) for r in result.recommendations],
    )


def _song_out(rec: Recommendation) -> SongOut:
    s = rec.song
    query = quote_plus(f"{s.title_original} {s.artist}")
    return SongOut(
        id=s.id,
        title=s.title,
        title_original=s.title_original,
        artist=s.artist,
        genre=s.genre,
        work=WorkOut(
            key=s.work.key, title=s.work.title, year=s.work.year, kind=s.work.kind, cover_url=s.work.cover_url
        ),
        story=s.story,
        scene=s.scene,
        reason=rec.reason,
        source_url=s.source_url,
        verified=s.verification == "sourced",
        listen_url=f"https://www.youtube.com/results?search_query={query}",
        artwork_url=s.artwork_url,
        apple_url=s.apple_url,
    )
