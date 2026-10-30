from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from api.dependencies import get_semantic_store
from memory.semantic_store import SemanticStore

router = APIRouter()

@router.get("/insights/summary")
async def get_global_insights(store: SemanticStore = Depends(get_semantic_store)):
    """
    Aggregates high-level intelligence across all processed sponsors.
    """
    try:
        all_sponsors = await store.get_all_sponsor_profiles(limit=1000)

        if not all_sponsors:
            return {"message": "No data available yet"}

        total_studies = sum(s["total_studies"] for s in all_sponsors)
        total_missing = sum(s["results_missing"] for s in all_sponsors)
        total_broken = sum(s["broken_promises"] for s in all_sponsors)

        # Identify top 3 most problematic sponsors
        top_risks = sorted(all_sponsors, key=lambda x: x["credibility_score"])[:3]

        return {
            "stats": {
                "total_sponsors": len(all_sponsors),
                "total_studies_indexed": total_studies,
                "global_missing_results": total_missing,
                "total_broken_promises": total_broken,
                "average_credibility": sum(s["credibility_score"] for s in all_sponsors) / len(all_sponsors)
            },
            "top_risks": top_risks
        }
    except Exception as e:
        return {"error": str(e)}
