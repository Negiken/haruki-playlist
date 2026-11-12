#!/usr/bin/env python3
"""曲のジャケット画像の候補を iTunes Search API から集めて backend/data/artwork.json に書く。

    python scripts/fetch_artwork.py            # まだ登録のない曲だけ探す
    python scripts/fetch_artwork.py --dry-run  # 候補を表示するだけ

- 画像そのものは保存しない。Apple の配信URLと、その曲の Apple Music ページを記録するだけ。
- すでに artwork.json にある項目は上書きしない（手で直した内容が残る）。
- 自動で選ぶのは「曲名が一致した最初の検索結果」。演奏者ちがいは起こりうるので、
  追加された項目の matched を目で確認し、違っていたら値を null にする（null は「画像なし」の印で、再検索もしない）。
- 小説の書影（works）は自動では探さない。Open Library の表紙IDを手で選んで書く。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
ARTWORK_PATH = DATA_DIR / "artwork.json"
USER_AGENT = "haruki-playlist-build/1.0"
INTERVAL_SEC = 3.5  # iTunes Search API は毎分20回程度まで
ARTWORK_SIZE = "600x600bb"

# 特定の演奏者を指さない書き方。検索語に入れると当たらなくなる
GENERIC_ARTIST = re.compile(r"民謡|スタンダード|作曲|作の")


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", text.lower())


def core_title(title_original: str) -> str:
    """'Années de pèlerinage – Le mal du pays' -> 'Le mal du pays' のように、曲そのものの名前を取り出す。"""
    title = re.sub(r"[（(][^）)]*[）)]", "", title_original)
    title = title.split(" – ")[-1]
    return title.split(",")[0].strip()


def search_terms(song: dict) -> list[str]:
    title = core_title(song["title_original"])
    artist = song["artist"]
    inner = re.search(r"（([^）]*)）", artist)
    lead = artist.split("（")[0].strip()
    terms = []
    if inner and not GENERIC_ARTIST.search(inner.group(1)):
        terms.append(f"{title} {inner.group(1).split('／')[0]}")  # かっこ内は演奏者。先頭の一人で探す
    if not GENERIC_ARTIST.search(lead):
        terms.append(f"{title} {lead}")
    terms.append(title)
    return terms


def itunes_search(term: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {"term": term, "media": "music", "entity": "song", "limit": 8, "country": "JP", "lang": "ja_jp"}
    )
    req = urllib.request.Request(f"https://itunes.apple.com/search?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)["results"]


def find(song: dict) -> dict | None:
    wanted = norm(core_title(song["title_original"]))
    for term in search_terms(song):
        results = itunes_search(term)
        time.sleep(INTERVAL_SEC)
        for r in results:
            if wanted and wanted in norm(r.get("trackName", "")) and r.get("artworkUrl100"):
                return {
                    "artwork_url": r["artworkUrl100"].replace("100x100bb", ARTWORK_SIZE),
                    "apple_url": r["trackViewUrl"].split("&uo=")[0],
                    "matched": f"{r['trackName']} — {r['artistName']}（{r['collectionName']}）",
                }
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    songs = json.loads((DATA_DIR / "songs.json").read_text(encoding="utf-8"))
    artwork = (
        json.loads(ARTWORK_PATH.read_text(encoding="utf-8")) if ARTWORK_PATH.exists() else {"works": {}, "songs": {}}
    )

    for song in songs:
        if song["id"] in artwork["songs"]:
            continue
        try:
            found = find(song)
        except OSError as e:
            print(f"!! {song['id']}: {e}", file=sys.stderr)
            continue
        print(f"{song['id']}: {song['title_original']} / {song['artist']}\n    -> {found['matched'] if found else 'なし'}")
        if found and not args.dry_run:
            artwork["songs"][song["id"]] = found
            ARTWORK_PATH.write_text(json.dumps(artwork, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
