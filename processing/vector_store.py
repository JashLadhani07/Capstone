
##############################################################################
# processing/vector_store.py
# Local persistent vector storage using ChromaDB
##############################################################################

import asyncio
import json
from pathlib import Path
from typing import Any

import chromadb

from processing.embedder import EmbeddedChunk
from config.logging_config import setup_logging

logger = setup_logging(__name__)

TOP_K_DEFAULT = 5

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CHROMA_DIR = DATA_DIR / "chroma"


class VectorStore:
    """
    Local ChromaDB storage for clinical studies and embedded chunks.
    """

    def __init__(self):
        self._client = None
        self._studies = None
        self._chunks = None

    async def __aenter__(self) -> "VectorStore":
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init(self) -> None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self._client = await asyncio.to_thread(
            chromadb.PersistentClient,
            path=str(CHROMA_DIR),
        )

        self._studies = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name="clinical_studies",
            metadata={"hnsw:space": "cosine"},
        )

        self._chunks = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name="clinical_chunks",
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "Local ChromaDB initialized | path=%s",
            CHROMA_DIR,
        )

        logger.info(
            "Existing records | studies=%s | chunks=%s",
            await asyncio.to_thread(self._studies.count),
            await asyncio.to_thread(self._chunks.count),
        )

    async def close(self) -> None:
        # PersistentClient persists data automatically.
        self._client = None
        self._studies = None
        self._chunks = None

    async def save_study(
        self,
        study_data: dict[str, Any],
    ) -> bool:
        nct_id = study_data.get("nct_id")

        if not nct_id:
            logger.warning("Skipping study without nct_id")
            return False

        metadata = {}

        for key, value in study_data.items():
            if key == "nct_id" or value is None:
                continue

            if isinstance(value, (list, dict)):
                value = json.dumps(value, default=str)
            elif hasattr(value, "isoformat"):
                value = value.isoformat()

            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value

        await asyncio.to_thread(
            self._studies.upsert,
            ids=[str(nct_id)],
            documents=[str(study_data.get("title") or nct_id)],
            metadatas=[metadata],
        )

        return True

    async def save_embedded_chunks(
        self,
        chunks: list[EmbeddedChunk],
    ) -> int:
        if not chunks:
            logger.warning("No embedded chunks to save")
            return 0

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            ids.append(str(chunk.chunk_id))
            documents.append(str(chunk.chunk_text))
            embeddings.append(
                [float(value) for value in chunk.embedding]
            )
            metadatas.append({
                "nct_id": str(chunk.nct_id),
                "chunk_index": int(chunk.chunk_index),
                "source": str(chunk.source or "unknown"),
            })

        # Check which chunk IDs already exist.
        existing_ids = set()

        for start in range(0, len(ids), 500):
            batch_ids = ids[start:start + 500]

            existing = await asyncio.to_thread(
                self._chunks.get,
                ids=batch_ids,
                include=[],
            )

            existing_ids.update(existing["ids"])

        # Skip existing chunks to avoid duplicate records.
        new_records = [
            (chunk_id, document, embedding, metadata)
            for chunk_id, document, embedding, metadata in zip(
                ids, documents, embeddings, metadatas
            )
            if chunk_id not in existing_ids
        ]

        if not new_records:
            logger.info(
                "All %s chunks already exist",
                len(chunks),
            )
            return 0

        saved_count = 0

        for start in range(0, len(new_records), 100):
            batch = new_records[start:start + 100]

            await asyncio.to_thread(
                self._chunks.add,
                ids=[record[0] for record in batch],
                documents=[record[1] for record in batch],
                embeddings=[record[2] for record in batch],
                metadatas=[record[3] for record in batch],
            )

            saved_count += len(batch)

        logger.info(
            "Local chunks saved | saved=%s | already_existing=%s",
            saved_count,
            len(chunks) - saved_count,
        )

        return saved_count

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = TOP_K_DEFAULT,
        source_filter: str | None = None,
        nct_id_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []

        if source_filter:
            filters.append({"source": source_filter})

        if nct_id_filter:
            filters.append({"nct_id": nct_id_filter})

        where = None

        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        count = await asyncio.to_thread(self._chunks.count)

        if count == 0 or top_k <= 0:
            return []

        query_args = {
            "query_embeddings": [
                [float(value) for value in query_embedding]
            ],
            "n_results": min(top_k, count),
            "include": ["documents", "metadatas", "distances"],
        }

        if where is not None:
            query_args["where"] = where

        result = await asyncio.to_thread(
            self._chunks.query,
            **query_args,
        )

        rows = []

        if not result["documents"] or not result["documents"][0]:
            return []

        for i, text in enumerate(result["documents"][0]):
            metadata = result["metadatas"][0][i] or {}

            rows.append({
                "nct_id": metadata.get("nct_id"),
                "chunk_text": text,
                "chunk_index": metadata.get("chunk_index"),
                "source": metadata.get("source"),
                "distance": result["distances"][0][i],
            })

        logger.info(
            "Local semantic search complete | results=%s",
            len(rows),
        )

        return rows

    async def get_chunk_count(self) -> int:
        return await asyncio.to_thread(self._chunks.count)

    async def study_exists(self, nct_id: str) -> bool:
        result = await asyncio.to_thread(
            self._chunks.get,
            where={"nct_id": str(nct_id)},
            limit=1,
            include=[],
        )

        return bool(result["ids"])
