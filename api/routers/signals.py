
##############################################################################
# api/routers/signals.py
#
# PURPOSE:
#   GET /api/v1/signals       -> list all signals
#   GET /api/v1/signals/{id}  -> get one specific signal
#
# STORAGE:
#   SQLite through SignalDatabase
##############################################################################

from fastapi import APIRouter, HTTPException, Query

from memory.signal_database import SignalDatabase
from config.logging_config import setup_logging

logger = setup_logging(__name__)
router = APIRouter()

database = SignalDatabase()
database.initialize()


@router.get(
    "/signals",
    summary="List all signals",
    description="Returns all generated signals with optional filters.",
    tags=["Signals"],
)
async def list_signals(
    agent: str = Query(
        default=None,
        description="Filter by agent name",
    ),
    signal_type: str = Query(
        default=None,
        description="Filter by signal type",
    ),
    status: str = Query(
        default=None,
        description="Filter by status: approved, pending, rejected",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum signals to return",
    ),
):
    """
    Returns signals from the SQLite database.

    Supports filtering by agent, signal_type and status.
    Results are ordered newest first.
    """

    try:
        filters = {
            "agent": agent,
            "signal_type": signal_type,
            "status": status,
        }

        filters = {
            key: value
            for key, value in filters.items()
            if value is not None
        }

        return database.get_signals(
            filters=filters,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Failed to retrieve signals: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve signals.",
        )


@router.get(
    "/signals/{signal_id}",
    summary="Get one signal by ID",
    tags=["Signals"],
)
async def get_signal(signal_id: str):
    """Returns the complete details of one specific signal."""

    try:
        signal = database.get_signal(signal_id)

        if not signal:
            raise HTTPException(
                status_code=404,
                detail=f"Signal {signal_id} not found.",
            )

        return signal

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to retrieve signal {signal_id}: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve signal.",
        )
