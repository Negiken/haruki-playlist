from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.models import MoodReading, Pick
from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app(Settings.from_env()))


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["songs"] >= 90
    assert body["llm_enabled"] is False


def test_works_lists_every_work(client):
    works = client.get("/api/works").json()
    assert len(works) == 16
    assert all(w["song_count"] > 0 for w in works)
    assert [w["year"] for w in works] == sorted(w["year"] for w in works)


def test_recommendations_with_rules(client):
    res = client.post("/api/recommendations", json={"text": "雨の夜、ひとりで物思いにふけっている"})
    assert res.status_code == 200
    body = res.json()
    assert body["engine"] == "rules"
    assert len(body["songs"]) == 1  # 既定は一曲だけ
    assert body["mood"]["tags"]
    song = body["songs"][0]
    assert {"artwork_url", "apple_url"} <= song.keys() and "cover_url" in song["work"]
    assert song["work"]["title"] and song["scene"] and song["reason"]
    assert song["source_url"].startswith("https://")
    assert song["listen_url"].startswith("https://www.youtube.com/results?search_query=")


def test_recommendations_with_claude_engine():
    class Primary:
        def read(self, text, count):
            return MoodReading("夜更かしの気分ですね。", {"night": 1.0}, (Pick("tsukuru-round-midnight", "真夜中に。"),))

    client = TestClient(create_app(Settings.from_env(), primary=Primary()))
    body = client.post("/api/recommendations", json={"text": "夜", "count": 1}).json()
    assert body["engine"] == "claude"
    assert body["mood"]["summary"] == "夜更かしの気分ですね。"
    assert body["songs"][0]["id"] == "tsukuru-round-midnight"
    assert body["songs"][0]["reason"] == "真夜中に。"

    again = client.post("/api/recommendations", json={"text": "夜", "exclude": ["tsukuru-round-midnight", "unknown-id"]})
    assert again.status_code == 200
    assert again.json()["songs"][0]["id"] != "tsukuru-round-midnight"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""}, {"text": "   "}, {"text": "あ" * 501}, {"text": "ok", "count": 0}, {"text": "ok", "count": 99}, {},
        {"text": "ok", "exclude": ["x"] * 31},
    ],
)
def test_invalid_requests_are_rejected(client, payload):
    assert client.post("/api/recommendations", json=payload).status_code == 422


def test_rate_limit_is_per_viewer_ip():
    settings = replace(Settings.from_env(), rate_limit_per_min=2)
    client = TestClient(create_app(settings))
    viewer_a = {"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}
    viewer_b = {"X-Forwarded-For": "9.9.9.9, 2.2.2.2"}  # 先頭は閲覧者が偽装できる値
    post = lambda headers: client.post("/api/recommendations", json={"text": "夜"}, headers=headers)

    assert post(viewer_a).status_code == 200
    assert post(viewer_a).status_code == 200
    assert post(viewer_a).status_code == 429
    assert post(viewer_b).status_code == 200


def test_frontend_is_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "村上春樹" in res.text
