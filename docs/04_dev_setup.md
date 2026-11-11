# 開発環境・起動・テスト

最終更新：2026-11-11

必要なのは **Python 3.11 以上**だけ（Node.js やビルド工程は不要）。以下は Windows の PowerShell での手順。

---

## 1. 環境構築

リポジトリのルートで：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
```

> フォルダが OneDrive 配下にある場合、`.venv` も同期対象になり重くなる。気になるときは `python -m venv C:\venvs\haruki` のように OneDrive の外に作る。

---

## 2. 起動

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

ブラウザで http://127.0.0.1:8000/ を開く。

この状態では API キーが無いので、**キーワード方式**で動く（画面に「キーワードで選曲」と出る）。

### Claude 方式で動かす

```powershell
$env:ANTHROPIC_API_KEY = "（自分のキー）"
uvicorn app.main:app --reload --port 8000
```

画面に「Claude が選曲」と出れば成功。サーバーのログに 1 回ごとのトークン使用量が出る：

```
claude usage: input=42 cache_read=9120 cache_write=0 output=380
```

2 回目以降に `cache_read` が 0 のままなら、システムプロンプトが毎回変わっている（`mood/claude.py` の `build_system_prompt` に時刻や乱数を入れていないか確認する）。

---

## 3. テスト

```powershell
cd backend
pytest -q
```

* 実際の Claude API は呼ばない（`tests/conftest.py` で無効化している）ので、キーなし・オフラインで通る
* 曲データの整合性チェックもここに含まれる

内容の一覧は `05_test_checklist.md` を参照。

---

## 4. 曲データの追加・修正

触るのは `backend/data/songs.json` だけ。

1. 既存の行をコピーして書き換える

   ```json
   {"id": "kafka-edelweiss", "title": "エーデルワイス", "title_original": "Edelweiss",
    "artist": "『サウンド・オブ・ミュージック』より", "genre": "pop", "work": "kafka",
    "scene": "（登場場面を自分の言葉で1〜2文）", "moods": ["nostalgic", "calm"],
    "source_url": "https://（確認した資料のURL）"}
   ```

2. 守ること
   * `id` は他と重ならない英数字とハイフン
   * `work` は `works.json` にある key、`moods` は `moods.json` にある key
   * `scene` は**小説本文を写さず要約する**。歌詞は書かない
   * 原作や資料で確認しきれていない場合は `"verification": "partial"` を付ける（画面に「要確認」と出る）
3. `pytest -q` を実行する。書式や key の間違いはここで分かる
4. `main` に push すれば自動で公開される

作品を増やす場合は `works.json` に 1 行足し、`tests/test_catalog.py` の作品数（12）を直す。

---

## 5. よくあるつまずき

| 症状 | 原因と対処 |
|---|---|
| 起動時に `CatalogError` | `songs.json` の内容が不正。メッセージに曲 ID と理由が出る |
| `json.decoder.JSONDecodeError` | カンマの過不足など JSON の書式ミス |
| 画面が古いまま | ブラウザのキャッシュ。Ctrl+F5 で再読み込み |
| ずっと「キーワードで選曲」 | `ANTHROPIC_API_KEY` が同じターミナルで設定されているか確認。ログに `Claude APIキーが無効です` などが出ていないか見る |
| Git Bash の `curl` で日本語を送ると `error parsing the body` | Git Bash が UTF-8 以外で送っている。ブラウザか PowerShell の `Invoke-RestMethod` で試す |
