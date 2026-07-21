from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.database import EventRepository
from app.vector_index import sync_vector_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize the Chroma vector index")
    parser.add_argument("--db", type=Path, help="Input SQLite path")
    parser.add_argument("--chroma-dir", type=Path, help="Chroma persistence directory")
    parser.add_argument("--provider", choices=("hash", "qwen"), help="Embedding provider")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = Settings.from_env()
    provider = args.provider or base.embedding_provider
    settings = Settings.from_env(
        db_path=(args.db or base.db_path).resolve(),
        chroma_dir=(args.chroma_dir or base.chroma_dir).resolve(),
        embedding_provider=provider,
    )
    repository = EventRepository(settings.db_path)
    result = sync_vector_index(settings, repository, provider=provider)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
