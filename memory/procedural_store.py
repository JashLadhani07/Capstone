
import asyncio
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone

import chromadb

from config.logging_config import setup_logging

logger = setup_logging(__name__)

DEFAULT_RULES = {
    "missing_results_agent": [
        "Flag a study as missing results ONLY if status is COMPLETED and results_posted is False and more than 12 months have passed since the completion date.",
        "Do NOT flag studies with status TERMINATED as missing results. Terminated trials are not legally required to post results in all circumstances.",
        "If enrollment was zero or very low (under 10 participants), note this in the signal but reduce confidence to 0.5.",
        "Always check the sponsor's track record before assigning a confidence score. A first-time missing result from a historically compliant sponsor warrants lower confidence than the same finding from a repeat offender.",
    ],

    "broken_promises_agent": [
        "Flag outcome switching ONLY when the PRIMARY outcome changes after enrollment has begun. Changes to secondary outcomes are less concerning and should not trigger a HIGH confidence signal.",
        "A change in outcome MEASUREMENT METHOD is different from a change in the outcome itself. Method changes may be legitimate protocol improvements — flag them at MEDIUM confidence, not HIGH.",
        "If a protocol amendment was filed BEFORE enrollment began, the outcome change is less suspicious. Assign MEDIUM confidence in this case.",
        "Always note the date of the change relative to the enrollment start date — this timing is the most important factor in assessing whether outcome switching is intentional.",
    ],

    "track_record_agent": [
        "A credibility score below 0.6 should trigger a LOW_CREDIBILITY signal. Between 0.6 and 0.75 is concerning but not alarming — note it in the analysis but do not generate a signal.",
        "Weight recent behaviour more heavily than old behaviour. A sponsor with 5 violations in the last 2 years is more concerning than one with 10 violations spread over 20 years.",
        "If a sponsor has fewer than 3 studies in our database, reduce confidence to 0.5. We do not have enough data to make a reliable judgment about their track record.",
        "Always distinguish between a sponsor's PRIMARY studies and COLLABORATIVE studies. Hold them more accountable for their primary studies.",
    ],

    "pattern_finder_agent": [
        "A cross-study pattern requires at least 3 studies to be meaningful. Two studies with similar issues may be coincidence. Three or more is a pattern worth flagging.",
        "When multiple companies are testing the same drug for the same condition, check whether any of them have hidden negative results from previous studies in our database.",
        "A drug that failed Phase 2 for condition A but is being retried in Phase 2 for condition B is worth flagging — especially if the mechanism of action is the same.",
        "Patterns across the same SPONSOR are more actionable than patterns across different sponsors. Same-sponsor patterns suggest systemic issues, not coincidence.",
    ],

    "side_effect_agent": [
        "A safety discrepancy between the official filing and a published paper is only meaningful if the paper was published AFTER the trial completed — not during it.",
        "Look specifically for cases where the filing says 'no serious adverse events' but published papers mention hospitalisations, discontinuations, or deaths. This is the highest-priority safety signal.",
        "If the discrepancy is minor, assign LOW confidence. If the discrepancy involves severity (mild vs serious), assign HIGH confidence.",
        "Always note whether the paper's authors are the same as the trial's investigators. Independent authors are more credible than sponsor-employed investigators.",
    ],

    "timeline_agent": [
        "Flag a delay ONLY if it exceeds 180 days beyond the stated completion date AND no amendment was filed explaining the extension.",
        "COVID-19 is a legitimate reason for delays between March 2020 and December 2022. Do not flag delays in this period as suspicious without additional evidence.",
        "A study that is recruiting past its stated completion date may simply have underestimated enrollment time. Focus on COMPLETED studies that are past their results posting deadline.",
        "Always compare the actual completion date against BOTH the original completion date AND any amended completion dates. Use the most recent amendment as the baseline.",
    ],
}


class ProceduralStore:

    def __init__(self):
        db_path = Path(__file__).resolve().parents[1] / "data" / "chroma"
        db_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(db_path))

        self._collection = self._client.get_or_create_collection(
            name="procedures",
            metadata={"hnsw:space": "cosine"}
        )

        self._lock = threading.RLock()

        logger.info("ProceduralStore initialised with ChromaDB")

    async def initialise_defaults(self) -> None:
        """Insert default rules without creating duplicates."""

        def _initialise():
            with self._lock:
                for agent_name, rules in DEFAULT_RULES.items():
                    for rule_text in rules:

                        procedure_id = str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                f"{agent_name}:{rule_text}"
                            )
                        )

                        existing = self._collection.get(
                            ids=[procedure_id]
                        )

                        if existing["ids"]:
                            continue

                        created_at = datetime.now(
                            timezone.utc
                        ).isoformat()

                        self._collection.add(
                            ids=[procedure_id],
                            documents=[rule_text],
                            metadatas=[{
                                "agent_name": agent_name,
                                "rule_type": "default",
                                "source": "default",
                                "created_at": created_at,
                                "updated_at": created_at,
                            }]
                        )

        await asyncio.to_thread(_initialise)

        logger.info(
            f"Default procedures initialised | "
            f"agents={list(DEFAULT_RULES.keys())}"
        )

    async def get_procedures(self, agent_name: str) -> list[str]:
        """Return all default and learned rules for an agent."""

        def _get():
            with self._lock:
                results = self._collection.get(
                    where={"agent_name": agent_name},
                    include=["documents", "metadatas"]
                )

            records = []

            for i, document in enumerate(results["documents"]):
                metadata = results["metadatas"][i]

                records.append((
                    metadata.get("created_at", ""),
                    document
                ))

            records.sort(key=lambda x: x[0])

            return [document for _, document in records]

        rules = await asyncio.to_thread(_get)

        logger.info(
            f"Procedures loaded | agent={agent_name} | "
            f"rules_count={len(rules)}"
        )

        return rules

    async def update_from_feedback(
        self,
        agent_name: str,
        rejection_reason: str
    ) -> str:
        """Save a new learned rule from human feedback."""

        procedure_id = str(uuid.uuid4())

        created_at = datetime.now(timezone.utc).isoformat()

        def _save():
            with self._lock:
                self._collection.add(
                    ids=[procedure_id],
                    documents=[rejection_reason],
                    metadatas=[{
                        "agent_name": agent_name,
                        "rule_type": "learned",
                        "source": "hitl_rejection",
                        "created_at": created_at,
                        "updated_at": created_at,
                    }]
                )

        await asyncio.to_thread(_save)

        logger.info(
            f"Procedure learned from feedback | "
            f"agent={agent_name} | "
            f"rule_preview='{rejection_reason[:80]}...' | "
            f"procedure_id={procedure_id}"
        )

        return procedure_id

    async def get_all_procedures_for_api(
        self,
        agent_name: str
    ) -> list[dict]:
        """Return all procedures with metadata for the API."""

        def _get():
            with self._lock:
                results = self._collection.get(
                    where={"agent_name": agent_name},
                    include=["documents", "metadatas"]
                )

            procedures = []

            for i, document in enumerate(results["documents"]):
                metadata = results["metadatas"][i]

                procedures.append({
                    "procedure_id": results["ids"][i],
                    "agent_name": metadata["agent_name"],
                    "rule_text": document,
                    "rule_type": metadata["rule_type"],
                    "source": metadata["source"],
                    "created_at": metadata["created_at"],
                })

            procedures.sort(key=lambda x: x["created_at"])

            return procedures

        return await asyncio.to_thread(_get)

    async def close(self) -> None:
        """Release the store references."""

        self._collection = None
        self._client = None

        logger.info("ProceduralStore closed")
