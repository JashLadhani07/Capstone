
##############################################################################
# graph/hitl.py
#
# PURPOSE:
#   Handles Human-in-the-Loop signal processing.
#
# STORAGE:
#   SQLite through memory.signal_database
#
# LEARNING:
#   Rejection feedback updates ProceduralStore.
##############################################################################

import uuid

from memory.signal_database import SignalDatabase
from memory.procedural_store import ProceduralStore
from config.logging_config import setup_logging

logger = setup_logging(__name__)


class HITLGate:

    CONFIDENCE_THRESHOLDS = {
        "broken_promises_agent": 0.99,
        "missing_results_agent": 0.99,
        "track_record_agent": 0.99,
        "pattern_finder_agent": 0.99,
        "side_effect_agent": 0.99,
        "timeline_agent": 0.99,
    }

    def __init__(self):

        self._database = SignalDatabase()
        self._database.initialize()

        self._procedural_store = ProceduralStore()

        logger.info("HITL Gate initialised | storage=SQLite")

    # ------------------------------------------------------------------
    # SIGNAL PROCESSING
    # ------------------------------------------------------------------

    async def process_signal(self, signal: dict) -> dict:
        """
        Route a signal based on its confidence score.

        High confidence:
            Save directly as approved.

        Low confidence:
            Send to human review queue.
        """

        agent_name = signal.get("agent", "")
        confidence = float(signal.get("confidence", 0.0))

        threshold = self.CONFIDENCE_THRESHOLDS.get(
            agent_name,
            0.65,
        )

        signal_id = signal.get("signal_id") or str(uuid.uuid4())

        signal["signal_id"] = signal_id

        if confidence >= threshold:

            await self._save_signal(signal)

            logger.info(
                f"Signal automatically approved | "
                f"agent={agent_name} | "
                f"confidence={confidence:.2f}"
            )

            return {
                "action": "saved",
                "signal_id": signal_id,
                "status": "approved",
            }

        return await self._send_to_review_queue(signal)

    # ------------------------------------------------------------------
    # AUTOMATIC APPROVAL
    # ------------------------------------------------------------------

    async def _save_signal(self, signal: dict) -> dict:
        """Save a high-confidence signal directly to SQLite."""

        signal_id = signal.get("signal_id") or str(uuid.uuid4())

        self._database.save_signal(
            signal_id=signal_id,
            signal=signal,
            status="approved",
        )

        logger.info(
            f"Signal saved | signal_id={signal_id}"
        )

        return {
            "action": "saved",
            "signal_id": signal_id,
        }

    # ------------------------------------------------------------------
    # HUMAN REVIEW QUEUE
    # ------------------------------------------------------------------

    async def _send_to_review_queue(self, signal: dict) -> dict:
        """Save a low-confidence signal and create a review entry."""

        signal_id = signal.get("signal_id") or str(uuid.uuid4())
        queue_id = str(uuid.uuid4())

        signal["signal_id"] = signal_id

        self._database.create_review(
            queue_id=queue_id,
            signal_id=signal_id,
            signal=signal,
        )

        logger.info(
            f"Signal sent to review | "
            f"signal_id={signal_id} | "
            f"queue_id={queue_id}"
        )

        return {
            "action": "sent_to_review",
            "signal_id": signal_id,
            "queue_id": queue_id,
            "status": "pending",
        }

    # ------------------------------------------------------------------
    # HUMAN DECISION PROCESSING
    # ------------------------------------------------------------------

    async def process_human_decision(
        self,
        queue_id: str,
        decision: str,
        reviewer: str = "analyst",
        rejection_reason: str = "",
        edit_summary: str = "",
    ) -> dict:
        """
        Process a human decision.

        Decisions:
            approve -> approve the signal
            reject  -> reject the signal
            edit    -> approve with corrected summary

        Rejection feedback is sent to ProceduralStore.
        """

        if decision not in ("approve", "reject", "edit"):
            raise ValueError(
                "Invalid decision. Use approve, reject or edit."
            )

        result = self._database.process_decision(
            queue_id=queue_id,
            decision=decision,
            reviewer=reviewer,
            rejection_reason=rejection_reason,
            edit_summary=edit_summary,
        )

        if not result:
            raise ValueError(
                f"Review not found or already processed: {queue_id}"
            )

        signal_id = result["signal_id"]
        agent_name = result["agent"]

        memory_updated = False

        # --------------------------------------------------------------
        # LEARNING FROM HUMAN REJECTIONS
        # --------------------------------------------------------------

        if decision == "reject" and rejection_reason.strip():

            try:
                await self._procedural_store.update_from_feedback(
                    agent_name=agent_name,
                    rejection_reason=rejection_reason,
                )

                memory_updated = True

                logger.info(
                    f"Procedural memory updated | "
                    f"agent={agent_name} | "
                    f"signal_id={signal_id}"
                )

            except Exception as e:

                logger.error(
                    f"Procedural memory update failed | "
                    f"agent={agent_name} | error={e}"
                )

                raise

        logger.info(
            f"Human decision recorded | "
            f"queue_id={queue_id} | "
            f"decision={decision} | "
            f"reviewer={reviewer}"
        )

        return {
            "success": True,
            "decision": decision,
            "signal_id": signal_id,
            "queue_id": queue_id,
            "memory_updated": memory_updated,
            "message": (
                "Signal rejected and agent memory updated."
                if memory_updated
                else f"Signal {decision}d successfully."
            ),
        }

    # ------------------------------------------------------------------
    # REVIEW QUEUE RETRIEVAL
    # ------------------------------------------------------------------

    async def get_review_queue(self) -> list[dict]:
        """Retrieve all signals awaiting human review."""

        return self._database.get_review_queue()

    # ------------------------------------------------------------------
    # SIGNAL LOOKUP
    # ------------------------------------------------------------------

    async def _get_agent_for_signal(
        self,
        signal_id: str,
    ) -> str | None:
        """Retrieve the agent associated with a signal."""

        signal = self._database.get_signal(signal_id)

        if not signal:
            return None

        return signal.get("agent")

    # ------------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------------

    async def close(self):
        """Close database resources."""

        self._database.close()

        logger.info("HITL Gate closed")
