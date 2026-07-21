from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen-plus"
DEFAULT_EMBEDDING_MODEL = "text-embedding-v2"
DEFAULT_VECTOR_COLLECTION = "history_events_v1"


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    storage_dir: Path = ROOT_DIR / "storage"
    db_path: Path = ROOT_DIR / "storage" / "history_events.db"
    chroma_dir: Path = ROOT_DIR / "storage" / "chroma"
    qwen_base_url: str = DEFAULT_QWEN_BASE_URL
    qwen_model: str = DEFAULT_QWEN_MODEL
    qwen_api_key: str | None = None
    use_llm: bool = True
    embedding_provider: str = "hash"
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    vector_collection: str = DEFAULT_VECTOR_COLLECTION
    vector_max_distance: float = 0.65
    retrieval_limit: int = 5
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, **overrides: object) -> "Settings":
        root = Path(str(overrides.pop("root_dir", ROOT_DIR))).resolve()
        storage = Path(
            str(overrides.pop("storage_dir", os.getenv("STORAGE_DIR", root / "storage")))
        ).resolve()
        values: dict[str, object] = {
            "root_dir": root,
            "data_dir": Path(
                str(overrides.pop("data_dir", os.getenv("DATA_DIR", root / "data")))
            ).resolve(),
            "storage_dir": storage,
            "db_path": Path(
                str(overrides.pop("db_path", os.getenv("DB_PATH", storage / "history_events.db")))
            ).resolve(),
            "chroma_dir": Path(
                str(overrides.pop("chroma_dir", os.getenv("CHROMA_DIR", storage / "chroma")))
            ).resolve(),
            "qwen_base_url": os.getenv("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL),
            "qwen_model": os.getenv("QWEN_MODEL", DEFAULT_QWEN_MODEL),
            "qwen_api_key": os.getenv("DASHSCOPE_API_KEY") or None,
            "use_llm": _as_bool(os.getenv("USE_LLM"), True),
            "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower(),
            "embedding_model": os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            "vector_collection": os.getenv("VECTOR_COLLECTION", DEFAULT_VECTOR_COLLECTION),
            "vector_max_distance": float(os.getenv("VECTOR_MAX_DISTANCE", "0.65")),
            "retrieval_limit": int(os.getenv("RETRIEVAL_LIMIT", "5")),
            "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
        }
        values.update(overrides)
        return cls(**values)

    @property
    def effective_collection(self) -> str:
        return f"{self.vector_collection}_{self.embedding_provider}"
