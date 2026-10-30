from fastapi import APIRouter
import json
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]

@router.get("/trials/all")
async def list_all_trials():
    studies_path = BASE_DIR / "data" / "processed" / "studies"
    papers_path = BASE_DIR / "data" / "processed" / "papers"

    studies = []
    if studies_path.exists():
        for f in studies_path.glob("*.json"):
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                    studies.append({
                        "id": data.get("nct_id") or f.stem,
                        "title": data.get("official_title") or data.get("title") or "Untitled Study",
                        "summary": data.get("brief_summary") or data.get("abstract") or "No summary available.",
                        "sponsor": data.get("sponsor") or data.get("lead_sponsor") or "Unknown Sponsor",
                        "status": data.get("overall_status") or "Unknown",
                        "phase": data.get("phase") or "N/A"
                    })
            except:
                continue

    papers = []
    if papers_path.exists():
        for f in papers_path.glob("*.json"):
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                    papers.append({
                        "id": data.get("id") or f.stem,
                        "title": data.get("title") or "Untitled Paper",
                        "summary": data.get("abstract") or data.get("summary") or "No abstract available.",
                        "journal": data.get("journal") or "Unknown Journal",
                        "year": data.get("year") or "N/A"
                    })
            except:
                continue

    return {
        "studies": studies,
        "papers": papers
    }
