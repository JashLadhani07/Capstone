
##############################################################################
# processing/embedder.py
# Local embeddings using Ollama + nomic-embed-text
##############################################################################

import asyncio
from dataclasses import dataclass

import httpx

from processing.chunker import TextChunk
from config.logging_config import setup_logging

logger = setup_logging(__name__)

BATCH_SIZE = 50
RETRY_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 2

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"


@dataclass
class EmbeddedChunk:
    chunk_id: str
    nct_id: str
    chunk_text: str
    chunk_index: int
    source: str
    word_count: int
    embedding: list[float]


class Embedder:
    def __init__(self):
        self._model = EMBEDDING_MODEL
        self._url = OLLAMA_URL

        logger.info(
            "Embedder initialized | provider=Ollama | model=%s",
            self._model,
        )

    async def embed_chunks(
        self,
        chunks: list[TextChunk],
    ) -> list[EmbeddedChunk]:
        if not chunks:
            logger.warning("No chunks provided for embedding")
            return []

        logger.info(
            "Starting local embedding | chunks=%s | batch_size=%s",
            len(chunks),
            BATCH_SIZE,
        )

        all_embedded = []
        batches = self._create_batches(chunks)

        async with httpx.AsyncClient(timeout=180.0) as client:
            for batch_num, batch in enumerate(batches, start=1):
                logger.info(
                    "Embedding batch %s/%s | chunks=%s",
                    batch_num,
                    len(batches),
                    len(batch),
                )

                embedded_batch = await self._embed_batch_with_retry(
                    client,
                    batch,
                    batch_num,
                )

                all_embedded.extend(embedded_batch)

        logger.info(
            "Embedding complete | embedded=%s | input=%s | skipped=%s",
            len(all_embedded),
            len(chunks),
            len(chunks) - len(all_embedded),
        )

        return all_embedded

    def _create_batches(
        self,
        chunks: list[TextChunk],
    ) -> list[list[TextChunk]]:
        return [
            chunks[i:i + BATCH_SIZE]
            for i in range(0, len(chunks), BATCH_SIZE)
        ]

    async def _embed_batch_with_retry(
        self,
        client: httpx.AsyncClient,
        batch: list[TextChunk],
        batch_num: int,
    ) -> list[EmbeddedChunk]:
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return await self._embed_batch(client, batch)

            except Exception as error:
                if attempt < RETRY_ATTEMPTS:
                    logger.warning(
                        "Embedding failed | batch=%s | attempt=%s/%s | "
                        "error=%s | retrying...",
                        batch_num,
                        attempt,
                        RETRY_ATTEMPTS,
                        error,
                    )
                    await asyncio.sleep(RETRY_SLEEP_SECONDS)
                else:
                    logger.exception(
                        "Embedding failed after %s attempts | batch=%s",
                        RETRY_ATTEMPTS,
                        batch_num,
                    )

        return []

    async def _embed_batch(
        self,
        client: httpx.AsyncClient,
        batch: list[TextChunk],
    ) -> list[EmbeddedChunk]:
        texts = [chunk.chunk_text for chunk in batch]

        response = await client.post(
            self._url,
            json={
                "model": self._model,
                "input": texts,
            },
        )

        response.raise_for_status()
        data = response.json()["embeddings"]

        if len(data) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} embeddings, received {len(data)}"
            )

        embedded_chunks = []

        for chunk, embedding in zip(batch, data):
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    nct_id=chunk.nct_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    source=chunk.source,
                    word_count=chunk.word_count,
                    embedding=[float(value) for value in embedding],
                )
            )

        logger.info(
            "Batch embedded | chunks=%s | dimensions=%s",
            len(embedded_chunks),
            len(embedded_chunks[0].embedding) if embedded_chunks else 0,
        )

        return embedded_chunks
