"""設定。すべて環境変数から読む（本番は /etc/haruki-playlist/env）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dir: Path
    version: str
    model: str
    llm_enabled: bool
    daily_llm_limit: int
    rate_limit_per_min: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            data_dir=Path(env.get("HARUKI_DATA_DIR", BACKEND_DIR / "data")),
            frontend_dir=Path(env.get("HARUKI_FRONTEND_DIR", REPO_DIR / "frontend")),
            version=env.get("HARUKI_VERSION", "dev"),
            model=env.get("HARUKI_MODEL", "claude-haiku-5-5"),
            # APIキーが無ければ Claude は使わず、ルールベースのみで動く
            llm_enabled=bool(env.get("ANTHROPIC_API_KEY")) and env.get("HARUKI_DISABLE_LLM") != "1",
            daily_llm_limit=int(env.get("HARUKI_DAILY_LLM_LIMIT", "300")),
            rate_limit_per_min=int(env.get("HARUKI_RATE_LIMIT_PER_MIN", "10")),
        )
