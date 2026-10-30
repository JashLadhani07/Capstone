
##############################################################################
# api/routers/review.py
#
# PURPOSE:
#   GET   /api/v1/review/queue  -> get pending review items
#   PATCH /api/v1/review/{id}   -> submit a human decision
#
# STORAGE:
#   SQLite through SignalDatabase
##############################################################################

from fastapi import APIRouter, Depends, HTTPException

from api.schemas import (
    ReviewQueueResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from api.dependencies import get_hitl_gate
from graph.hitl import HITLGate
from memory.signal_database import SignalDatabase
from config.logging_config import setup_logging

logger = setup_logging(__name__)
router = APIRouter()

database = SignalDatabase()
database.initialize()


@router.get(
    "/review/queue",
    response_model=ReviewQueueResponse,
    summary="Get pending human review queue",
    description=(
        "Returns all signals waiting for human analyst review, "
        "ordered by confidence ascending (most uncertain first)."
    ),
    tags=["Human Review"],
)
async def get_review_queue(
    hitl_gate: HITLGate = Depends(get_hitl_gate),
):
    """Returns pending review items and review statistics."""

    try:
        queue_items = await hitl_gate.get_review_queue()

        stats = database.get_review_stats()

        return ReviewQueueResponse(
            queue=queue_items,
            total_pending=stats.get("pending", 0),
            total_approved=stats.get("approved", 0),
            total_rejected=stats.get("rejected", 0),
        )

    except Exception as e:
        logger.error(f"get_review_queue failed | error={e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve review queue.",
        )


@router.patch(
    "/review/{queue_id}",
    response_model=ReviewDecisionResponse,
    summary="Submit a human review decision",
    description=(
        "Approve, reject, or edit a queued signal. "
        "Rejections can trigger the procedural memory learning loop."
    ),
    tags=["Human Review"],
)
async def submit_review_decision(
    queue_id: str,
    request: ReviewDecisionRequest,
    hitl_gate: HITLGate = Depends(get_hitl_gate),
):
    """
    Submit a human analyst's decision.

    APPROVE -> signal is approved.
    EDIT    -> signal summary is corrected and approved.
    REJECT  -> signal is rejected; feedback can update procedural memory.
    """

    if request.decision not in ("approve", "reject", "edit"):
        raise HTTPException(
            status_code=422,
            detail="decision must be 'approve', 'reject', or 'edit'",
        )

    try:
        result = await hitl_gate.process_human_decision(
            queue_id=queue_id,
            decision=request.decision,
            reviewer=request.reviewer,
            rejection_reason=request.rejection_reason,
            edit_summary=request.edit_summary,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Review not found"),
            )

        memory_updated = result.get("memory_updated", False)

        logger.info(
            f"Review decision submitted | "
            f"queue_id={queue_id} | "
            f"decision={request.decision} | "
            f"memory_updated={memory_updated}"
        )

        return ReviewDecisionResponse(
            success=True,
            decision=request.decision,
            signal_id=result.get("signal_id", ""),
            queue_id=queue_id,
            memory_updated=memory_updated,
            message=(
                "Procedural memory updated — rejection feedback "
                "was saved for the agent."
                if memory_updated
                else f"Signal {request.decision}d successfully."
            ),
        )

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except Exception as e:
        logger.error(
            f"submit_review_decision failed | error={e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process review decision.",
        )
