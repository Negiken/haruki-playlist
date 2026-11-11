"""アプリの組み立て。部品を作って配線するだけ。"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.routes import build_router
from .catalog.repository import load_catalog
from .config import Settings
from .mood.analyzer import MoodAnalyzer
from .mood.rule_based import RuleBasedAnalyzer
from .service.limits import DailyBudget, RateLimiter
from .service.recommendation_service import RecommendationService


def create_app(settings: Settings | None = None, primary: MoodAnalyzer | None = None) -> FastAPI:
    """primary を渡すとテスト用の解析器に差し替えられる。"""
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    catalog = load_catalog(settings.data_dir)

    if primary is None and settings.llm_enabled:
        from .mood.claude import ClaudeAnalyzer  # APIキーが無い環境では SDK を初期化しない

        primary = ClaudeAnalyzer(catalog, settings.model)

    service = RecommendationService(
        catalog,
        fallback=RuleBasedAnalyzer(catalog.moods),
        primary=primary,
        budget=DailyBudget(settings.daily_llm_limit),
    )

    app = FastAPI(title="村上春樹プレイリスト", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(
        build_router(catalog, service, RateLimiter(settings.rate_limit_per_min), settings.version)
    )
    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
