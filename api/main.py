
##############################################################################
# api/main.py
#
# PURPOSE:
#   Main FastAPI application entry point.
#
# STORAGE:
#   SQLite  -> Signals and HITL reviews
#   ChromaDB -> Episodic, semantic and procedural memory
#
# FRONTEND:
#   Jinja2 Templates + Static CSS/JS
##############################################################################

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import analysis, signals, review, memory, frontend, trials_explorer, db_explorer, insights

from api.dependencies import (
    get_procedural_store,
    get_episodic_store,
    get_semantic_store,
)

from memory.signal_database import SignalDatabase

from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# DATABASE
# --------------------------------------------------------------------------

signal_database = SignalDatabase()


# --------------------------------------------------------------------------
# APPLICATION LIFESPAN
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("=" * 60)
    logger.info("MOSAIC API starting up...")
    logger.info("=" * 60)

    # Initialise SQLite
    try:
        signal_database.initialize()
        app.state.signal_database = signal_database

        logger.info("SQLite signal database initialised")

    except Exception as e:
        logger.exception(
            f"Failed to initialise SQLite database | error={e}"
        )
        raise

    # Initialise procedural memory defaults
    try:
        procedural_store = get_procedural_store()

        await procedural_store.initialise_defaults()

        logger.info("Default agent procedures initialised")

    except Exception as e:
        logger.error(
            f"Failed to initialise procedures | error={e}"
        )

    logger.info("MOSAIC API ready | version=0.1.0")
    logger.info("=" * 60)

    yield

    logger.info("MOSAIC API shutting down...")
    logger.info("MOSAIC API shutdown complete")


# --------------------------------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------------------------------

app = FastAPI(
    title="MOSAIC — Clinical Trial Intelligence API",
    description=(
        "Multi-Agent Operating System for AI Cognition. "
        "Detects research integrity signals across clinical trials "
        "using 6 specialist AI agents."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if settings.api_env == "development" else []
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# STATIC FILES
# --------------------------------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


# --------------------------------------------------------------------------
# API ROUTERS
# --------------------------------------------------------------------------

app.include_router(analysis.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(trials_explorer.router, prefix="/api/v1")
app.include_router(db_explorer.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")


# --------------------------------------------------------------------------
# FRONTEND ROUTER
# --------------------------------------------------------------------------

app.include_router(frontend.router)


# --------------------------------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------------------------------

@app.get(
    "/api/v1/health",
    summary="System health check",
    description="Returns the application and storage status.",
    tags=["System"],
)
async def health_check():

    database_status = "connected"

    episodes_count = 0
    sponsor_count = 0
    procedures_count = 0
    signals_count = 0

    try:
        # Check SQLite
        signal_database.get_review_stats()

        signals = signal_database.get_signals(
            filters={},
            limit=200,
        )

        signals_count = len(signals)

        # Check ChromaDB stores
        episodic_store = get_episodic_store()
        semantic_store = get_semantic_store()
        procedural_store = get_procedural_store()

        episodes_count = await episodic_store.count_episodes()

        sponsor_profiles = await semantic_store.get_all_sponsor_profiles(
            limit=100000
        )

        sponsor_count = len(sponsor_profiles)

        procedures = []

        for agent_name in (
            "missing_results_agent",
            "broken_promises_agent",
            "track_record_agent",
            "pattern_finder_agent",
            "side_effect_agent",
            "timeline_agent",
        ):

            agent_procedures = (
                await procedural_store.get_all_procedures_for_api(
                    agent_name
                )
            )

            procedures.extend(agent_procedures)

        procedures_count = len(procedures)

    except Exception as e:

        database_status = f"disconnected: {str(e)}"

        logger.error(
            f"Health check storage error | error={e}"
        )

    return {
        "status": (
            "healthy"
            if database_status == "connected"
            else "degraded"
        ),
        "app": "MOSAIC",
        "version": "0.1.0",
        "database": database_status,
        "storage": {
            "relational": "SQLite",
            "vector": "ChromaDB",
        },
        "details": {
            "signals_count": signals_count,
            "episodes_count": episodes_count,
            "sponsor_profiles_count": sponsor_count,
            "procedures_count": procedures_count,
        },
    }
