
import asyncio
import uuid
from pathlib import Path
from datetime import datetime

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings

from config.logging_config import setup_logging

logger = setup_logging(__name__)


class EpisodicStore:

    def __init__(self):
        self._client = None
        self._collection = None

        self._db_path = Path(__file__).resolve().parents[1] / "data" / "chroma"

        self._embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            encode_kwargs={"normalize_embeddings": True},
        )

        logger.info("EpisodicStore initialised")

    def _ensure_collection(self):

        if self._collection is not None:
            return

        self._client = chromadb.PersistentClient(
            path=str(self._db_path)
        )

        self._collection = self._client.get_or_create_collection(
            name="episodes",
            metadata={"hnsw:space": "cosine"},
        )

        logger.info("Episodic ChromaDB collection ready")

    async def _embed(self, text: str) -> list[float]:

        return await asyncio.to_thread(
            self._embedding_model.embed_query,
            text,
        )

    async def save_episode(
        self,
        agent_name: str,
        content: str,
        nct_id: str | None = None,
        outcome: str | None = None,
    ) -> str:

        self._ensure_collection()

        episode_id = str(uuid.uuid4())
        embedding = await self._embed(content)

        metadata = {
            "agent_name": agent_name,
            "created_at": datetime.utcnow().isoformat(),
        }

        if nct_id is not None:
            metadata["nct_id"] = nct_id

        if outcome is not None:
            metadata["outcome"] = outcome

        self._collection.add(
            ids=[episode_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
        )

        logger.info(
            f"Episode saved | "
            f"agent={agent_name} | "
            f"nct_id={nct_id} | "
            f"outcome={outcome} | "
            f"episode_id={episode_id}"
        )

        return episode_id

    async def search_episodes(
        self,
        query: str,
        agent_name: str | None = None,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> list[dict]:

        self._ensure_collection()

        query_embedding = await self._embed(query)

        count = self._collection.count()

        if count == 0:
            return []

        search_args = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, count),
            "include": ["documents", "metadatas", "distances"],
        }

        if agent_name:
            search_args["where"] = {
                "agent_name": agent_name
            }

        results = self._collection.query(**search_args)

        episodes = []

        for i, episode_id in enumerate(results["ids"][0]):

            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            similarity = 1 - distance

            if similarity < min_similarity:
                continue

            episodes.append({
                "episode_id": episode_id,
                "agent_name": metadata["agent_name"],
                "nct_id": metadata.get("nct_id"),
                "content": results["documents"][0][i],
                "outcome": metadata.get("outcome"),
                "similarity": round(float(similarity), 3),
                "created_at": metadata["created_at"],
            })

        logger.info(
            f"Episode search complete | "
            f"query='{query[:50]}...' | "
            f"agent_filter={agent_name} | "
            f"results_found={len(episodes)}"
        )

        return episodes

    async def get_recent_episodes(
        self,
        agent_name: str | None = None,
        limit: int = 10,
    ) -> list[dict]:

        self._ensure_collection()

        search_args = {
            "include": ["documents", "metadatas"],
        }

        if agent_name:
            search_args["where"] = {
                "agent_name": agent_name
            }

        results = self._collection.get(**search_args)

        episodes = []

        for i, episode_id in enumerate(results["ids"]):

            metadata = results["metadatas"][i]

            episodes.append({
                "episode_id": episode_id,
                "agent_name": metadata["agent_name"],
                "nct_id": metadata.get("nct_id"),
                "content": results["documents"][i],
                "outcome": metadata.get("outcome"),
                "created_at": metadata["created_at"],
            })

        episodes.sort(
            key=lambda x: x["created_at"],
            reverse=True,
        )

        return episodes[:limit]

    async def count_episodes(
        self,
        agent_name: str | None = None,
    ) -> int:

        self._ensure_collection()

        if agent_name is None:
            return self._collection.count()

        results = self._collection.get(
            where={"agent_name": agent_name},
            include=[],
        )

        return len(results["ids"])

    async def close(self) -> None:

        self._collection = None
        self._client = None

        logger.info("EpisodicStore closed")
