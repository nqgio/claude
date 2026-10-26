import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="listing-test-")
os.environ["APP_DATA_DIR"] = _tmp
os.environ["APP_ENV_FILE"] = str(Path(_tmp) / "test.env")
for k in list(os.environ):
    if k.startswith(("EBAY_", "ANTHROPIC_API_KEY")):
        del os.environ[k]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import settings_store as st  # noqa: E402
from app.db import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    st.reset_cache()
    from app.providers import sample

    sample.OVERRIDES.clear()
    yield


@pytest.fixture
def sample_source():
    st.update({"product_source": "sample", "search_keywords": ["kitchen gadgets"], "amazon_cache_hours": 0})
    from app.blocklist import seed_if_empty

    seed_if_empty()
    yield
