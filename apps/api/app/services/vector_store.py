from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.postgres import get_connection
from app.services.embeddings import (
    GeminiEmbeddingFunction,
    HashingEmbeddingFunction,
)

try:
    import chromadb
except ImportError:  # pragma: no cover - optional dependency
    chromadb = None

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass(slots=True)
class SearchResult:
    id: str
    document_id: str
    source_name: str
    chunk_index: int
    text: str
    score: float


def _vector_literal(vector: list[float]) -> str:
    """Render a float list in pgvector's bracket-literal syntax (``[0.1, 0.2, ...]``)."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


_SCOPE_SYNC = """
UPDATE material_chunks mc
SET course_id = c.id,
    university_id = col.university_id
FROM materials m
JOIN topics t ON t.id = m.topic_id
JOIN courses c ON c.id = t.course_id
LEFT JOIN departments d ON d.id = c.department_id
LEFT JOIN colleges col ON col.id = d.college_id
WHERE mc.document_id = m.id::text AND mc.document_id = %s
"""


class PgVectorBackend:
    """pgvector-backed chunk store used for real semantic search."""

    def __init__(self) -> None:
        self.embedding_function = GeminiEmbeddingFunction()

    def upsert_document(
        self,
        document_id: str,
        source_name: str,
        chunks: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        del metadata
        vectors = self.embedding_function.embed_documents(chunks)
        rows = [
            (document_id, source_name, index, chunk, _vector_literal(vector))
            for index, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM material_chunks WHERE document_id = %s", (document_id,))
            cursor.executemany(
                """
                INSERT INTO material_chunks
                    (document_id, source_name, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                rows,
            )
            if document_id:
                cursor.execute(_SCOPE_SYNC, (document_id,))
                if cursor.rowcount == 0:
                    logger.warning(
                        "Chunks for document %s have no course scope (no matching "
                        "material row); they will be invisible to institution-scoped "
                        "retrieval.",
                        document_id,
                    )
            conn.commit()
        return len(rows)

    def query(
        self,
        text: str,
        top_k: int = 5,
        course_id: str | None = None,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        vector = self.embedding_function.embed_query(text)
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM match_material_chunks(%s::vector, %s, %s, %s)",
                (_vector_literal(vector), document_id, top_k, course_id),
            )
            rows = cursor.fetchall()
        results: list[SearchResult] = []
        for row in rows:
            results.append(
                SearchResult(
                    id=str(row["id"]),
                    document_id=str(row["document_id"]),
                    source_name=str(row["source_name"]),
                    chunk_index=int(row["chunk_index"]),
                    text=str(row["content"]),
                    score=float(row["similarity"]),
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM material_chunks WHERE document_id = %s", (document_id,))
            conn.commit()


def _chroma_where(
    course_id: str | None, document_id: str | None
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if course_id:
        clauses.append({"course_id": course_id})
    if document_id:
        clauses.append({"document_id": document_id})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class VectorStore:
    """Chunk vector store with a pgvector primary backend and ChromaDB fallback.

    Backend selection follows ``VECTOR_STORE_BACKEND``:

    * ``pgvector`` (or ``auto`` with ``GEMINI_API_KEY`` set) stores embeddings in the
      ``material_chunks`` Postgres table via HNSW search.
    * ``chromadb`` (or ``auto`` without a Gemini key) keeps the legacy local ChromaDB
      collection, using hashing embeddings.
    * If the pgvector migration hasn't been applied, any pgvector call fails cleanly and
      queries/upserts fall back to ChromaDB so nothing breaks.
    """

    def __init__(
        self,
        persist_directory: str | Path = "./tmp/chromadb",
        collection_name: str = "vylix_documents",
        backend: str | None = None,
    ) -> None:
        self.embedding_function = HashingEmbeddingFunction()
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self._fallback_records: list[dict[str, Any]] = []
        self._client = None
        self._collection = None
        self._pg_backend: PgVectorBackend | None = None

        selected = (backend or settings.vector_store_backend or "auto").lower()
        if selected not in ("auto", "pgvector", "chromadb"):
            logger.warning("Unknown VECTOR_STORE_BACKEND %r; using 'auto'.", selected)
            selected = "auto"
        if selected == "pgvector":
            if settings.gemini_api_key:
                self._pg_backend = PgVectorBackend()
                logger.info(
                    "Vector store: pgvector (%s)",
                    self._pg_backend.embedding_function.name(),
                )
            else:
                logger.warning(
                    "pgvector backend requested but GEMINI_API_KEY is unset; using ChromaDB.",
                )
        elif selected == "auto" and settings.gemini_api_key:
            self._pg_backend = PgVectorBackend()
            logger.info(
                "Vector store: pgvector (%s)",
                self._pg_backend.embedding_function.name(),
            )

        if self._pg_backend is None:
            logger.info("Vector store: ChromaDB (%s)", self.embedding_function.name())
        self._init_chroma()

    def _init_chroma(self) -> None:
        if chromadb is None:
            return
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_directory))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
        )

    def upsert_document(
        self,
        document_id: str,
        source_name: str,
        chunks: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if self._pg_backend is not None:
            try:
                return self._pg_backend.upsert_document(
                    document_id, source_name, chunks, metadata or {}
                )
            except Exception:
                logger.exception(
                    "pgvector upsert failed for %s; falling back to ChromaDB", document_id
                )
        return self._chroma_upsert(document_id, source_name, chunks, metadata or {})

    def _chroma_upsert(
        self,
        document_id: str,
        source_name: str,
        chunks: list[str],
        metadata: dict[str, Any],
    ) -> int:
        chunk_ids = [f"{document_id}-{index}" for index in range(len(chunks))]
        if self._collection is not None:
            self._collection.upsert(
                ids=chunk_ids,
                documents=chunks,
                metadatas=[
                    {
                        "document_id": document_id,
                        "source_name": source_name,
                        "chunk_index": index,
                        **metadata,
                    }
                    for index in range(len(chunks))
                ],
            )
        else:
            self._fallback_records.extend(
                {
                    "id": chunk_ids[index],
                    "document_id": document_id,
                    "source_name": source_name,
                    "chunk_index": index,
                    "text": chunk,
                    "metadata": metadata,
                }
                for index, chunk in enumerate(chunks)
            )
        return len(chunks)

    def query(
        self,
        text: str,
        top_k: int = 5,
        course_id: str | None = None,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        if self._pg_backend is not None:
            try:
                return self._pg_backend.query(
                    text, top_k=top_k, course_id=course_id, document_id=document_id
                )
            except Exception:
                logger.exception("pgvector query failed; falling back to ChromaDB")
        return self._chroma_query(text, top_k, course_id=course_id, document_id=document_id)

    def _chroma_query(
        self,
        text: str,
        top_k: int,
        course_id: str | None = None,
        document_id: str | None = None,
    ) -> list[SearchResult]:
        if self._collection is not None:
            result = self._collection.query(
                query_texts=[text],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
                where=_chroma_where(course_id, document_id),
            )
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            search_results: list[SearchResult] = []
            for index, document in enumerate(documents):
                metadata = metadatas[index] or {}
                search_results.append(
                    SearchResult(
                        id=str(result.get("ids", [[]])[0][index]),
                        document_id=str(metadata.get("document_id", "")),
                        source_name=str(metadata.get("source_name", "")),
                        chunk_index=int(metadata.get("chunk_index", index)),
                        text=document,
                        score=float(1.0 - distances[index]) if distances else 0.0,
                    )
                )
            return search_results

        return self._fallback_query(text, top_k)

    def delete_document(self, document_id: str) -> None:
        """Remove all chunks for a document from every active backend."""
        if self._pg_backend is not None:
            try:
                self._pg_backend.delete_document(document_id)
            except Exception:
                logger.exception("pgvector delete failed for %s", document_id)
        if self._collection is not None:
            try:
                self._collection.delete(where={"document_id": document_id})
            except Exception:
                logger.warning("ChromaDB delete failed for %s", document_id)
        else:
            self._fallback_records = [
                record
                for record in self._fallback_records
                if record["document_id"] != document_id
            ]

    def _fallback_query(self, text: str, top_k: int) -> list[SearchResult]:
        if not self._fallback_records:
            return []

        texts = [record["text"] for record in self._fallback_records]
        matrix = self.embedding_function([text] + texts)
        query_vector = np.asarray(matrix[0], dtype=float)
        document_vectors = np.asarray(matrix[1:], dtype=float)
        similarities = document_vectors @ query_vector
        ranking = np.argsort(-similarities)[:top_k]

        results: list[SearchResult] = []
        for index in ranking:
            record = self._fallback_records[int(index)]
            results.append(
                SearchResult(
                    id=record["id"],
                    document_id=record["document_id"],
                    source_name=record["source_name"],
                    chunk_index=record["chunk_index"],
                    text=record["text"],
                    score=float(similarities[int(index)]),
                )
            )
        return results
