from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.database import initialize_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the SQLite and FTS5 event database")
    parser.add_argument("--db", type=Path, help="Output SQLite path")
    parser.add_argument("--data", type=Path, help="Input history_events.jsonl path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    db_path = (args.db or settings.db_path).resolve()
    data_path = (args.data or settings.data_dir / "history_events.jsonl").resolve()
    result = initialize_database(db_path, data_path)
    print(json.dumps({"database": str(db_path), **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
