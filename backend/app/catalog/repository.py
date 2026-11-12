"""楽曲カタログ（JSON）の読み込みと整合性チェック。

データは読み取り専用で、起動時に一度だけ読み込む。
不正なデータは起動時（＝CI のテスト時）に必ず失敗させる。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..domain.models import Mood, Song, Work

GENRES = {"jazz", "pop", "classical", "other"}
VERIFICATIONS = {"sourced", "partial"}


class CatalogError(ValueError):
    pass


@dataclass
class Catalog:
    moods: dict[str, Mood]
    works: dict[str, Work]
    songs: tuple[Song, ...]

    def __post_init__(self) -> None:
        self._by_id = {s.id: s for s in self.songs}

    def song(self, song_id: str) -> Song | None:
        return self._by_id.get(song_id)


def load_catalog(data_dir: Path) -> Catalog:
    moods = {
        m["key"]: Mood(m["key"], m["label"], tuple(m.get("keywords", ())))
        for m in _read(data_dir / "moods.json")
    }
    artwork = _read_artwork(data_dir / "artwork.json")
    works = {
        w["key"]: Work(
            w["key"], w["title"], int(w["year"]), w["kind"], w["source_url"],
            cover_url=(artwork["works"].get(w["key"]) or {}).get("cover_url"),
        )
        for w in _read(data_dir / "works.json")
    }
    unknown_works = set(artwork["works"]) - set(works)
    if unknown_works:
        raise CatalogError(f"artwork.json: 未定義の作品です: {sorted(unknown_works)}")

    songs: list[Song] = []
    seen: set[str] = set()
    for raw in _read(data_dir / "songs.json"):
        sid = raw.get("id", "?")
        if sid in seen:
            raise CatalogError(f"曲IDが重複しています: {sid}")
        seen.add(sid)
        if raw.get("work") not in works:
            raise CatalogError(f"{sid}: 未定義の作品です: {raw.get('work')}")
        unknown = [m for m in raw.get("moods", []) if m not in moods]
        if unknown or not raw.get("moods"):
            raise CatalogError(f"{sid}: 気分タグが不正です: {unknown or '空'}")
        if raw.get("genre") not in GENRES:
            raise CatalogError(f"{sid}: ジャンルが不正です: {raw.get('genre')}")
        verification = raw.get("verification", "sourced")
        if verification not in VERIFICATIONS:
            raise CatalogError(f"{sid}: verification が不正です: {verification}")
        for key in ("title", "title_original", "artist", "scene"):
            if not raw.get(key):
                raise CatalogError(f"{sid}: {key} が空です")

        work = works[raw["work"]]
        art = artwork["songs"].get(sid) or {}
        songs.append(
            Song(
                id=sid,
                title=raw["title"],
                title_original=raw["title_original"],
                artist=raw["artist"],
                genre=raw["genre"],
                work=work,
                scene=raw["scene"],
                moods=tuple(raw["moods"]),
                source_url=raw.get("source_url") or work.source_url,
                story=raw.get("story"),
                verification=verification,
                artwork_url=art.get("artwork_url"),
                apple_url=art.get("apple_url"),
            )
        )
    if not songs:
        raise CatalogError("曲が1件もありません")
    unknown_songs = set(artwork["songs"]) - seen
    if unknown_songs:
        raise CatalogError(f"artwork.json: 未定義の曲です: {sorted(unknown_songs)}")
    return Catalog(moods=moods, works=works, songs=tuple(songs))


def _read_artwork(path: Path) -> dict:
    """画像のURL集。無くても動く（画像なしで表示される）。値が null の項目は「画像なし」の印。"""
    if not path.exists():
        return {"works": {}, "songs": {}}
    with path.open(encoding="utf-8") as f:
        artwork = json.load(f)
    for group in ("works", "songs"):
        for key, entry in artwork.setdefault(group, {}).items():
            for field, url in (entry or {}).items():
                if field.endswith("_url") and not str(url).startswith("https://"):
                    raise CatalogError(f"artwork.json: {key}.{field} は https のURLにしてください")
    return artwork


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
