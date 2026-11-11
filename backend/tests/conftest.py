import os

# テストでは実際の Claude API を絶対に呼ばない
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["HARUKI_DISABLE_LLM"] = "1"

import pytest

from app.catalog.repository import Catalog, load_catalog
from app.config import BACKEND_DIR


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog(BACKEND_DIR / "data")
