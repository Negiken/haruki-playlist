import json
from collections import Counter

import pytest

from app.catalog.repository import CatalogError, load_catalog
from app.config import BACKEND_DIR


def test_real_catalog_loads(catalog):
    assert len(catalog.songs) >= 90
    assert len(catalog.works) == 16


def test_every_work_has_songs(catalog):
    counts = Counter(s.work.key for s in catalog.songs)
    assert all(counts[key] >= 3 for key in catalog.works), counts


def test_every_mood_is_used_by_enough_songs(catalog):
    counts = Counter(m for s in catalog.songs for m in s.moods)
    assert all(counts[key] >= 5 for key in catalog.moods), counts


def test_every_song_has_a_source(catalog):
    assert all(s.source_url.startswith("https://") for s in catalog.songs)


def _copy_data(tmp_path, mutate):
    src = BACKEND_DIR / "data"
    for name in ("moods.json", "works.json", "songs.json"):
        data = json.loads((src / name).read_text(encoding="utf-8"))
        if name == "songs.json":
            data = data[:3]
            mutate(data)
        (tmp_path / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "mutate",
    [
        lambda songs: songs.append(dict(songs[0])),  # ID重複
        lambda songs: songs[0].update(work="nonexistent"),
        lambda songs: songs[0].update(moods=["nonexistent"]),
        lambda songs: songs[0].update(moods=[]),
        lambda songs: songs[0].update(genre="enka"),
        lambda songs: songs[0].update(scene=""),
    ],
)
def test_invalid_catalog_is_rejected(tmp_path, mutate):
    with pytest.raises(CatalogError):
        load_catalog(_copy_data(tmp_path, mutate))
