
import json
import httpx

from langchain_core.tools import tool

from config.settings import settings
from processing.vector_store import VectorStore
from memory.episodic_store import EpisodicStore
from memory.semantic_store import SemanticStore


async def _embed_text(text: str):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "http://localhost:11434/api/embed",
            json={
                "model": "nomic-embed-text",
                "input": [text]
            }
        )

        response.raise_for_status()

        data = response.json()
        return data["embeddings"][0]


@tool
async def search_studies_by_meaning(
    query: str,
    top_k: int = 5
) -> str:
    """Search locally stored clinical trials using semantic similarity."""

    store = VectorStore()

    try:
        query_embedding = await _embed_text(query)

        await store.init()

        results = await store.search(
            query_embedding=query_embedding,
            top_k=top_k
        )

        return json.dumps({
            "query": query,
            "results": results,
            "count": len(results)
        }, default=str)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "query": query
        })

    finally:
        await store.close()


@tool
async def search_past_episodes(
    query: str,
    agent_name: str = "",
    top_k: int = 5
) -> str:
    """Search previous agent episodes using semantic similarity."""

    store = EpisodicStore()

    try:
        results = await store.search_episodes(
            query=query,
            agent_name=agent_name or None,
            top_k=top_k
        )

        return json.dumps({
            "query": query,
            "results": results,
            "count": len(results)
        }, default=str)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "query": query
        })

    finally:
        await store.close()


@tool
async def save_episode(
    agent_name: str,
    content: str,
    nct_id: str = "",
    outcome: str = ""
) -> str:
    """Save an agent's reasoning or result as episodic memory."""

    store = EpisodicStore()

    try:
        episode_id = await store.save_episode(
            agent_name=agent_name,
            content=content,
            nct_id=nct_id or None,
            outcome=outcome or None
        )

        return json.dumps({
            "success": True,
            "episode_id": episode_id
        }, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

    finally:
        await store.close()


@tool
async def get_sponsor_profile(sponsor: str) -> str:
    """Retrieve historically similar studies associated with a sponsor."""

    store = VectorStore()

    try:
        embedding = await _embed_text(sponsor)

        await store.init()

        results = await store.search(
            query_embedding=embedding,
            top_k=20
        )

        seen = set()
        filtered = []

        for result in results:
            nct_id = result.get("nct_id")

            if nct_id and nct_id not in seen:
                seen.add(nct_id)
                filtered.append(result)

        return json.dumps({
            "sponsor": sponsor,
            "results": filtered,
            "count": len(filtered)
        }, default=str)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "sponsor": sponsor
        })

    finally:
        await store.close()


@tool
async def update_sponsor_profile(
    sponsor: str,
    profile_update: str
) -> str:
    """Store a sponsor-related observation as episodic memory."""

    content = (
        f"Sponsor profile update for {sponsor}: {profile_update}"
    )

    store = EpisodicStore()

    try:
        episode_id = await store.save_episode(
            agent_name="sponsor_profile",
            content=content,
            outcome=profile_update
        )

        return json.dumps({
            "success": True,
            "sponsor": sponsor,
            "episode_id": episode_id
        }, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

    finally:
        await store.close()


@tool
async def get_low_credibility_sponsors(
    threshold: float = 0.6,
    min_studies: int = 3
) -> str:
    """Find sponsors whose credibility is below a given threshold."""

    store = SemanticStore()

    try:
        sponsors = await store.get_low_credibility_sponsors(
            threshold=threshold,
            min_studies=min_studies
        )

        return json.dumps(sponsors, default=str)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        })


ALL_SEARCH_TOOLS = [
    search_studies_by_meaning,
    search_past_episodes,
    save_episode,
    get_sponsor_profile,
    update_sponsor_profile,
    get_low_credibility_sponsors
]
