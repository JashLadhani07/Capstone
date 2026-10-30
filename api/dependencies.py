
##############################################################################
# api/dependencies.py
#
# PURPOSE:
#   Creates and manages shared resources used by API endpoints.
#
# RESOURCES:
#   HITLGate       -> SQLite signal and HITL management
#   EpisodicStore  -> ChromaDB episodic memory
#   ProceduralStore -> ChromaDB procedural memory
#   SemanticStore  -> ChromaDB semantic memory
#   MOSAIC Graph   -> Compiled LangGraph workflow
##############################################################################

from functools import lru_cache

from graph.hitl import HITLGate
from graph.graph_builder import mosaic_graph

from memory.episodic_store import EpisodicStore
from memory.procedural_store import ProceduralStore
from memory.semantic_store import SemanticStore


# --------------------------------------------------------------------------
# HITL GATE
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_hitl_gate() -> HITLGate:
    """
    Returns one shared HITLGate instance.

    The HITLGate manages:
        - Signal processing
        - Confidence-based approval
        - Human review queue
        - Human decisions
        - Procedural memory feedback

    Signal and review data are stored in SQLite.
    """

    return HITLGate()


# --------------------------------------------------------------------------
# EPISODIC MEMORY
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_episodic_store() -> EpisodicStore:
    """
    Returns the shared EpisodicStore instance.

    Stores and retrieves past analysis episodes using ChromaDB.
    """

    return EpisodicStore()


# --------------------------------------------------------------------------
# PROCEDURAL MEMORY
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_procedural_store() -> ProceduralStore:
    """
    Returns the shared ProceduralStore instance.

    Stores agent procedures and feedback-based learning information.
    """

    return ProceduralStore()


# --------------------------------------------------------------------------
# SEMANTIC MEMORY
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_semantic_store() -> SemanticStore:
    """
    Returns the shared SemanticStore instance.

    Stores and retrieves sponsor-related semantic information.
    """

    return SemanticStore()


# --------------------------------------------------------------------------
# LANGGRAPH WORKFLOW
# --------------------------------------------------------------------------

def get_graph():
    """
    Returns the compiled MOSAIC LangGraph workflow.

    mosaic_graph is already compiled at module level
    in graph_builder.py.

    Therefore, no additional caching is required.
    """

    return mosaic_graph
