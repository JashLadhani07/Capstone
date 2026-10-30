
##############################################################################
# processing/run_processing.py
# Loads parsed studies, creates chunks, generates embeddings, and saves locally.
##############################################################################

import asyncio

from ingestion.document_parser import ParsedStudy
from ingestion.local_store import LocalStore
from processing.chunker import Chunker
from processing.embedder import Embedder
from processing.vector_store import VectorStore
from config.logging_config import setup_logging

logger = setup_logging(__name__)


async def run_processing():
    print("Starting local study processing...", flush=True)

    local_store = LocalStore()
    chunker = Chunker()
    embedder = Embedder()

    logger.info("Loading parsed studies from LocalStore...")
    studies = await local_store.list_processed_studies()
    logger.info("Found %s studies in LocalStore", len(studies))

    if not studies:
        logger.warning("No processed studies found. Nothing to process.")
        return

    studies_saved = 0
    chunks_created = 0
    chunks_saved = 0
    failures = 0

    logger.info("Initializing local ChromaDB vector store...")

    async with VectorStore() as vector_store:
        for index, nct_id in enumerate(studies, start=1):
            try:
                logger.info(
                    "Processing study %s/%s | nct_id=%s",
                    index,
                    len(studies),
                    nct_id,
                )

                parsed_data = await local_store.load_parsed_study(nct_id)

                if not parsed_data:
                    logger.warning("Could not load study %s", nct_id)
                    failures += 1
                    continue

                if isinstance(parsed_data, dict):
                    study = ParsedStudy(**parsed_data)
                else:
                    study = parsed_data

                if hasattr(study, "model_dump"):
                    study_data = study.model_dump(mode="json")
                elif hasattr(study, "dict"):
                    study_data = study.dict()
                else:
                    study_data = vars(study)

                study_data["nct_id"] = (
                    study_data.get("nct_id") or nct_id
                )

                logger.info("Saving study metadata...")
                success = await vector_store.save_study(study_data)

                if success:
                    studies_saved += 1

                logger.info("Creating chunks...")
                chunks = chunker.chunk_study(study)

                if not chunks:
                    logger.warning("No chunks created for %s", nct_id)
                    continue

                chunks_created += len(chunks)

                logger.info(
                    "Created %s chunks for %s",
                    len(chunks),
                    nct_id,
                )

                logger.info("Generating embeddings...")
                embedded_chunks = await embedder.embed_chunks(chunks)

                if not embedded_chunks:
                    logger.warning(
                        "No embeddings generated for %s",
                        nct_id,
                    )
                    continue

                logger.info("Saving embedded chunks to local ChromaDB...")
                saved = await vector_store.save_embedded_chunks(
                    embedded_chunks
                )

                chunks_saved += saved

                logger.info(
                    "Study complete | nct_id=%s | chunks=%s | saved=%s",
                    nct_id,
                    len(embedded_chunks),
                    saved,
                )

            except Exception:
                failures += 1
                logger.exception(
                    "Failed to process study %s",
                    nct_id,
                )

        total_stored = await vector_store.get_chunk_count()

    print("\nProcessing finished.", flush=True)
    print(f"Studies found: {len(studies)}", flush=True)
    print(f"Studies saved: {studies_saved}", flush=True)
    print(f"Chunks created: {chunks_created}", flush=True)
    print(f"New chunks saved: {chunks_saved}", flush=True)
    print(f"Total chunks in ChromaDB: {total_stored}", flush=True)
    print(f"Failed studies: {failures}", flush=True)

    logger.info("Local processing pipeline finished.")


if __name__ == "__main__":
    asyncio.run(run_processing())
