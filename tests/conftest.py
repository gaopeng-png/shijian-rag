from __future__ import annotations

import pytest

from app.config import ROOT_DIR, Settings
from app.database import EventRepository, initialize_database
from app.vector_index import sync_vector_index


@pytest.fixture(scope="session")
def test_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    storage = tmp_path_factory.mktemp("shijian_storage")
    settings = Settings(
        root_dir=ROOT_DIR,
        data_dir=ROOT_DIR / "data",
        storage_dir=storage,
        db_path=storage / "events.db",
        chroma_dir=storage / "chroma",
        use_llm=False,
        embedding_provider="hash",
    )
    initialize_database(settings.db_path, settings.data_dir / "history_events.jsonl")
    sync_vector_index(settings, EventRepository(settings.db_path), provider="hash")
    return settings
