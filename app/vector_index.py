from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import Settings
from app.database import EventRepository
from app.embeddings import create_embeddings


@dataclass(slots=True)
class VectorHit:
    event_id: str
    distance: float


def _load_knowledge(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _knowledge_hash(doc: dict[str, str]) -> str:
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sync_vector_index(
    settings: Settings,
    repository: EventRepository,
    provider: str | None = None,
) -> dict[str, int | str]:
    selected = (provider or settings.embedding_provider).lower()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    collection = f"{settings.vector_collection}_{selected}"
    store = Chroma(
        collection_name=collection,
        persist_directory=str(settings.chroma_dir),
        embedding_function=create_embeddings(settings, selected),
        collection_metadata={"hnsw:space": "cosine"},
    )

    desired: dict[str, tuple[Document, str]] = {}
    for event in repository.list_events():
        desired[event.id] = (
            Document(
                page_content=event.embedding_text(),
                metadata={
                    "doc_type": "event",
                    "event_id": event.id,
                    "name": event.name,
                    "year": event.year,
                    "region": event.region,
                    "scope": event.scope,
                    "content_hash": event.content_hash,
                },
            ),
            event.content_hash,
        )

    for doc in _load_knowledge(settings.data_dir / "knowledge_docs.jsonl"):
        doc_id = doc["id"]
        content_hash = _knowledge_hash(doc)
        desired[doc_id] = (
            Document(
                page_content=f"{doc['title']}：{doc['text']}",
                metadata={
                    "doc_type": "knowledge",
                    "knowledge_id": doc_id,
                    "title": doc["title"],
                    "content_hash": content_hash,
                },
            ),
            content_hash,
        )

    existing = store.get(include=["metadatas"])
    existing_hashes = {
        doc_id: str(metadata.get("content_hash", ""))
        for doc_id, metadata in zip(existing.get("ids", []), existing.get("metadatas", []), strict=False)
        if metadata
    }
    stale = sorted(set(existing_hashes) - set(desired))
    changed = sorted(
        doc_id
        for doc_id, (_, content_hash) in desired.items()
        if existing_hashes.get(doc_id) != content_hash
    )
    if stale:
        store.delete(ids=stale)
    if changed:
        already_present = [doc_id for doc_id in changed if doc_id in existing_hashes]
        if already_present:
            store.delete(ids=already_present)
        store.add_documents(
            documents=[desired[doc_id][0] for doc_id in changed],
            ids=changed,
        )
    return {
        "provider": selected,
        "collection": collection,
        "added_or_updated": len(changed),
        "deleted": len(stale),
        "total": len(desired),
    }


class VectorIndex:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store: Chroma | None = None
        self.error = ""
        sqlite_path = settings.chroma_dir / "chroma.sqlite3"
        if not sqlite_path.is_file():
            self.error = "vector index not built"
            return
        try:
            self.store = Chroma(
                collection_name=settings.effective_collection,
                persist_directory=str(settings.chroma_dir),
                embedding_function=create_embeddings(settings),
            )
            probe = self.store.get(limit=1, include=[])
            if not probe.get("ids"):
                self.store = None
                self.error = "vector collection is empty"
        except Exception as exc:  # vector retrieval must not break exact/FTS retrieval
            self.store = None
            self.error = str(exc)

    @property
    def ready(self) -> bool:
        return self.store is not None

    def search(self, query: str, limit: int = 20) -> list[VectorHit]:
        if self.store is None or not query.strip():
            return []
        try:
            results = self.store.similarity_search_with_score(
                query,
                k=limit,
                filter={"doc_type": "event"},
            )
        except Exception as exc:
            self.error = str(exc)
            return []
        hits: list[VectorHit] = []
        for document, distance in results:
            event_id = str(document.metadata.get("event_id", ""))
            if event_id and float(distance) <= self.settings.vector_max_distance:
                hits.append(VectorHit(event_id=event_id, distance=float(distance)))
        return hits
