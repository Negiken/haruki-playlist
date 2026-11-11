import random
from datetime import date

from app.domain.models import MoodReading, Pick
from app.mood.analyzer import AnalyzerError
from app.mood.rule_based import RuleBasedAnalyzer
from app.service.limits import DailyBudget, RateLimiter
from app.service.recommendation_service import RecommendationService


class FakeAnalyzer:
    def __init__(self, reading=None, error=None):
        self.reading, self.error, self.calls = reading, error, 0

    def read(self, text, count):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reading


def _service(catalog, primary=None, budget=None):
    return RecommendationService(
        catalog, fallback=RuleBasedAnalyzer(catalog.moods), primary=primary, budget=budget,
        rng=random.Random(0),
    )


def test_uses_claude_picks_in_order(catalog):
    picks = (Pick("nw-norwegian-wood", "理由A"), Pick("after-dark-five-spot", "理由B"))
    primary = FakeAnalyzer(MoodReading("要約", {"night": 1.0}, picks))
    result = _service(catalog, primary).recommend("なんでも", 2)
    assert result.engine == "claude"
    assert [(r.song.id, r.reason) for r in result.recommendations] == [
        ("nw-norwegian-wood", "理由A"),
        ("after-dark-five-spot", "理由B"),
    ]


def test_invalid_duplicate_and_overconcentrated_picks_are_dropped_then_topped_up(catalog):
    picks = (
        Pick("does-not-exist", "x"),
        Pick("after-dark-five-spot", "a"),
        Pick("after-dark-five-spot", "dup"),
        Pick("after-dark-more", "b"),
        Pick("after-dark-jealousy", "同じ作品の3曲目"),
    )
    primary = FakeAnalyzer(MoodReading("要約", {"night": 1.0}, picks))
    result = _service(catalog, primary).recommend("夜", 5)
    ids = [r.song.id for r in result.recommendations]
    assert ids[:2] == ["after-dark-five-spot", "after-dark-more"]
    assert len(ids) == 5 and len(set(ids)) == 5
    assert "does-not-exist" not in ids and "after-dark-jealousy" not in ids
    assert sum(1 for r in result.recommendations if r.song.work.key == "after_dark") == 2


def test_falls_back_to_rules_when_claude_fails(catalog):
    primary = FakeAnalyzer(error=AnalyzerError("connection"))
    result = _service(catalog, primary).recommend("雨の日でしんみり", 5)
    assert result.engine == "rules"
    assert len(result.recommendations) == 5
    assert "rainy" in result.reading.weights


def test_falls_back_to_rules_when_daily_budget_is_exhausted(catalog):
    primary = FakeAnalyzer(MoodReading("要約", {}, (Pick("nw-julia", "r"),)))
    service = _service(catalog, primary, DailyBudget(1))
    assert service.recommend("a", 1).engine == "claude"
    assert service.recommend("a", 1).engine == "rules"
    assert primary.calls == 1


def test_without_primary_uses_rules(catalog):
    service = _service(catalog)
    assert not service.llm_enabled
    assert service.recommend("楽しい", 3).engine == "rules"


def test_daily_budget_resets_on_new_day():
    days = iter([date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 2)])
    budget = DailyBudget(1, today=lambda: next(days))
    assert budget.try_consume()
    assert not budget.try_consume()
    assert budget.try_consume()


def test_rate_limiter_sliding_window():
    now = [0.0]
    limiter = RateLimiter(2, window_sec=60, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 61.0
    assert limiter.allow("a")
