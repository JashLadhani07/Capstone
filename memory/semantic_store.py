
import threading
from pathlib import Path
from datetime import datetime
from typing import Any

import chromadb

from config.logging_config import setup_logging

logger = setup_logging(__name__)

_write_lock = threading.RLock()


class SemanticStore:

    def __init__(self):
        self._client = None
        self._collection = None

        self._db_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "chroma"
        )

        logger.info("SemanticStore initialised")

    def _ensure_collection(self):

        if self._collection is not None:
            return

        self._client = chromadb.PersistentClient(
            path=str(self._db_path)
        )

        self._collection = self._client.get_or_create_collection(
            name="sponsor_profiles"
        )

        logger.info("Sponsor profiles ChromaDB collection ready")

    def _format_profile(self, metadata: dict) -> dict[str, Any]:

        return {
            "sponsor": metadata["sponsor"],
            "credibility_score": float(metadata["credibility_score"]),
            "total_studies": int(metadata["total_studies"]),
            "results_posted": int(metadata["results_posted"]),
            "results_missing": int(metadata["results_missing"]),
            "broken_promises": int(metadata["broken_promises"]),
            "avg_delay_days": float(metadata["avg_delay_days"]),
            "last_updated": str(metadata["last_updated"]),
        }

    async def register_ingested_sponsors(
        self,
        sponsor_counts: dict[str, int],
    ) -> None:

        self._ensure_collection()

        registered = 0
        now = datetime.utcnow().isoformat()

        with _write_lock:

            for sponsor, total_studies in sponsor_counts.items():

                sponsor = sponsor.strip()

                if not sponsor:
                    continue

                result = self._collection.get(
                    ids=[sponsor],
                    include=["metadatas"],
                )

                if result["ids"]:

                    profile = self._format_profile(
                        result["metadatas"][0]
                    )

                    profile["total_studies"] = max(
                        profile["total_studies"],
                        total_studies,
                    )

                else:

                    profile = {
                        "sponsor": sponsor,
                        "total_studies": total_studies,
                        "results_posted": 0,
                        "results_missing": 0,
                        "broken_promises": 0,
                        "avg_delay_days": 0.0,
                        "credibility_score": 0.5,
                        "last_updated": now,
                    }

                profile["last_updated"] = now

                self._collection.upsert(
                    ids=[sponsor],
                    documents=[f"Profile for {sponsor}"],
                    metadatas=[profile],
                )

                registered += 1

        logger.info(
            f"Sponsor profiles registered | count={registered}"
        )

    async def get_sponsor_profile(
        self,
        sponsor: str,
    ) -> dict[str, Any] | None:

        self._ensure_collection()

        result = self._collection.get(
            ids=[sponsor],
            include=["metadatas"],
        )

        if not result["ids"]:
            logger.info(
                f"No profile found for sponsor | sponsor={sponsor}"
            )
            return None

        return self._format_profile(result["metadatas"][0])

    async def update_sponsor_knowledge(
        self,
        sponsor: str,
        results_posted: bool | None = None,
        had_broken_promise: bool = False,
        delay_days: int = 0,
    ) -> None:

        self._ensure_collection()

        sponsor = sponsor.strip()

        if not sponsor:
            return

        with _write_lock:

            result = self._collection.get(
                ids=[sponsor],
                include=["metadatas"],
            )

            now = datetime.utcnow().isoformat()

            if result["ids"]:

                profile = self._format_profile(
                    result["metadatas"][0]
                )

            else:

                profile = {
                    "sponsor": sponsor,
                    "total_studies": 0,
                    "results_posted": 0,
                    "results_missing": 0,
                    "broken_promises": 0,
                    "avg_delay_days": 0.0,
                    "credibility_score": 0.5,
                    "last_updated": now,
                }

            old_total = profile["total_studies"]

            profile["total_studies"] += 1

            if results_posted is not None:

                if results_posted:
                    profile["results_posted"] += 1
                else:
                    profile["results_missing"] += 1

            if had_broken_promise:
                profile["broken_promises"] += 1

            if delay_days > 0:
                known_delays = (
                    profile["results_posted"]
                    + profile["results_missing"]
                )

                profile["avg_delay_days"] = (
                    (
                        profile["avg_delay_days"] * max(known_delays - 1, 0)
                    ) + float(delay_days)
                ) / max(known_delays, 1)

            known_results = (
                profile["results_posted"]
                + profile["results_missing"]
            )

            if known_results > 0:
                compliance_rate = (
                    profile["results_posted"] / known_results
                )

                credibility = (
                    compliance_rate * 0.7
                ) - (
                    profile["broken_promises"] * 0.1
                )

                profile["credibility_score"] = max(
                    0.0,
                    min(1.0, credibility),
                )

            profile["last_updated"] = now

            self._collection.upsert(
                ids=[sponsor],
                documents=[f"Profile for {sponsor}"],
                metadatas=[profile],
            )

        logger.info(
            f"Sponsor knowledge updated | "
            f"sponsor={sponsor} | "
            f"results_posted={results_posted} | "
            f"broken_promise={had_broken_promise} | "
            f"delay_days={delay_days}"
        )

    async def get_low_credibility_sponsors(
        self,
        threshold: float = 0.6,
        min_studies: int = 3,
    ) -> list[dict]:

        self._ensure_collection()

        result = self._collection.get(
            include=["metadatas"],
        )

        sponsors = []

        for metadata in result["metadatas"]:

            profile = self._format_profile(metadata)

            if (
                profile["credibility_score"] < threshold
                and profile["total_studies"] >= min_studies
            ):
                sponsors.append(profile)

        sponsors.sort(
            key=lambda x: x["credibility_score"]
        )

        logger.info(
            f"Low credibility sponsors found | "
            f"count={len(sponsors)} | "
            f"threshold={threshold} | "
            f"min_studies={min_studies}"
        )

        return sponsors

    async def get_all_sponsor_profiles(
        self,
        limit: int = 50,
    ) -> list[dict]:

        self._ensure_collection()

        result = self._collection.get(
            include=["metadatas"],
        )

        sponsors = [
            self._format_profile(metadata)
            for metadata in result["metadatas"]
        ]

        sponsors.sort(
            key=lambda x: x["credibility_score"]
        )

        return sponsors[:limit]

    async def sponsor_exists(
        self,
        sponsor: str,
    ) -> bool:

        self._ensure_collection()

        result = self._collection.get(
            ids=[sponsor],
            include=[],
        )

        return len(result["ids"]) > 0

    async def close(self) -> None:

        self._collection = None
        self._client = None

        logger.info("SemanticStore closed")
