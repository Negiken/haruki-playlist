import random
from collections import Counter

from app.domain.recommender import MAX_PER_WORK, recommend
from app.mood.rule_based import RuleBasedAnalyzer


def _recommend(catalog, weights, count=5, seed=1, **kw):
    return recommend(weights, catalog.songs, catalog.moods, count, random.Random(seed), **kw)


def test_recommend_prefers_matching_moods(catalog):
    recs = _recommend(catalog, {"night": 2.0, "lonely": 1.0})
    assert len(recs) == 5
    assert all({"night", "lonely"} & set(r.song.moods) for r in recs)
    assert all("気分に重なる" in r.reason for r in recs)


def test_recommend_limits_songs_per_work(catalog):
    for seed in range(20):
        recs = _recommend(catalog, {"night": 3.0}, count=8, seed=seed)  # night は『アフターダーク』に集中
        per_work = Counter(r.song.work.key for r in recs)
        assert max(per_work.values()) <= MAX_PER_WORK


def test_recommend_respects_exclusions_and_existing_work_counts(catalog):
    first = _recommend(catalog, {"drive": 1.0}, count=3)
    ids = [r.song.id for r in first]
    more = _recommend(
        catalog, {"drive": 1.0}, count=3, exclude_ids=ids, work_counts={"dance": MAX_PER_WORK}
    )
    assert not set(ids) & {r.song.id for r in more}
    assert all(r.song.work.key != "dance" for r in more)


def test_recommend_without_weights_still_returns_songs(catalog):
    recs = _recommend(catalog, {}, count=5)
    assert len(recs) == 5
    assert len({r.song.id for r in recs}) == 5


def test_rule_based_detects_moods(catalog):
    reading = RuleBasedAnalyzer(catalog.moods).read("仕事で疲れた。眠れない夜で、なんだか寂しい")
    assert {"tired", "night", "lonely"} <= set(reading.weights)
    assert "気分として受け取りました" in reading.summary


def test_rule_based_handles_english_and_case(catalog):
    reading = RuleBasedAnalyzer(catalog.moods).read("So LONELY tonight")
    assert {"lonely", "night"} <= set(reading.weights)


def test_rule_based_without_match_returns_empty_weights(catalog):
    reading = RuleBasedAnalyzer(catalog.moods).read("qwerty")
    assert reading.weights == {}
    assert reading.picks == ()
