from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.mood.analyzer import AnalyzerError
from app.mood.claude import ClaudeAnalyzer, _ReadingOut, build_system_prompt


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def _response(stop_reason="end_turn", parsed=None):
    usage = SimpleNamespace(
        input_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=5
    )
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed, usage=usage)


def _analyzer(catalog, messages):
    return ClaudeAnalyzer(catalog, "claude-haiku-5-5", client=SimpleNamespace(messages=messages))


def test_system_prompt_is_deterministic_and_lists_every_song(catalog):
    prompt = build_system_prompt(catalog)
    assert prompt == build_system_prompt(catalog)
    assert all(s.id in prompt for s in catalog.songs)
    assert all(m in prompt for m in catalog.moods)


def test_read_maps_structured_output(catalog):
    parsed = _ReadingOut(moods=["night", "unknown-mood", "lonely"], picks=["after-dark-five-spot", "nw-julia"])
    messages = FakeMessages(_response(parsed=parsed))
    reading = _analyzer(catalog, messages).read("眠れない", 5)

    assert reading.summary == "「深夜」「孤独」の気分として受け取りました。"
    assert reading.weights == {"night": 2.0, "lonely": 1.0}
    assert [p.song_id for p in reading.picks] == ["after-dark-five-spot", "nw-julia"]

    sent = messages.kwargs
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["thinking"] == {"type": "disabled"}  # 応答時間のため。書かせる量を最小にする
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "眠れない" in sent["messages"][0]["content"]
    assert "眠れない" not in sent["system"][0]["text"]  # 可変部分はキャッシュ対象の外


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_response_raises(catalog, stop_reason):
    with pytest.raises(AnalyzerError):
        _analyzer(catalog, FakeMessages(_response(stop_reason=stop_reason))).read("x", 5)


def test_api_errors_are_wrapped(catalog):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=request)
    with pytest.raises(AnalyzerError):
        _analyzer(catalog, FakeMessages(error=error)).read("x", 5)
