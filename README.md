# 村上春樹プレイリスト

いまの気分を文章で書くと、村上春樹の小説に登場する音楽（ジャズ・洋楽・クラシック）を、出典と登場場面つきで提案する Web アプリ。

- 対象：『風の歌を聴け』から『騎士団長殺し』までの 16 作品・142 曲
- 選曲：Claude（Haiku）が気分を読んで選ぶ。使えないときはキーワード方式に自動で切り替わる
- 構成：FastAPI + 静的フロント → EC2 1 台、前段に CloudFront
- 公開：`main` に push すると GitHub Actions がテスト・デプロイ・動作確認まで行う

## すぐ動かす

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
cd backend
pytest -q
uvicorn app.main:app --reload --port 8000   # http://127.0.0.1:8000/
```

## ドキュメント

[docs/01_index.md](docs/01_index.md) から。公開手順は [docs/06_how_to_deploy_first_time.md](docs/06_how_to_deploy_first_time.md)。
