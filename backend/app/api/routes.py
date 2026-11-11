"""HTTP エンドポイント。ここにはロジックを書かない（検証 → サービス呼び出し → 変換のみ）。"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from ..catalog.repository import Catalog
from ..service.limits import RateLimiter
from ..service.recommendation_service import RecommendationService
from .schemas import (
    HealthResponse,
    RecommendationRequest,
    RecommendationResponse,
    WorkSummary,
    to_response,
)


def client_ip(request: Request) -> str:
    """CloudFront が付け足した X-Forwarded-For の末尾＝閲覧者のIP。

    オリジンは CloudFront からの通信しか受けないので、末尾の値は偽装できない。
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def build_router(
    catalog: Catalog,
    service: RecommendationService,
    limiter: RateLimiter,
    version: str,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", version=version, songs=len(catalog.songs), llm_enabled=service.llm_enabled
        )

    @router.get("/works", response_model=list[WorkSummary])
    def works() -> list[WorkSummary]:
        counts = Counter(s.work.key for s in catalog.songs)
        return [
            WorkSummary(
                key=w.key, title=w.title, year=w.year, kind=w.kind,
                song_count=counts[w.key], source_url=w.source_url,
            )
            for w in sorted(catalog.works.values(), key=lambda w: w.year)
        ]

    @router.post("/recommendations", response_model=RecommendationResponse)
    def recommendations(body: RecommendationRequest, request: Request) -> RecommendationResponse:
        if not limiter.allow(client_ip(request)):
            raise HTTPException(status_code=429, detail="少し時間をおいてから、もう一度お試しください。")
        return to_response(service.recommend(body.text, body.count), catalog)

    return router
