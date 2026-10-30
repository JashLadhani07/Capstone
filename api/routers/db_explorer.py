from fastapi import APIRouter
import json
import os
from pathlib import Path

router = APIRouter()

@router.get("/all")
async def list_all_processed_data():
    # Use absolute path to avoid any parent resolution issues
    processed_dir = Path(r"C:\Users\Atharva Ghadigaonkar\OneDrive\Desktop\MAAJ with UI\data\processed")

    all_files = []
    if processed_dir.exists():
        # Walk through all subdirectories
        for root, dirs, files in os.walk(processed_dir):
            for file in files:
                if file.endswith(".json"):
                    path = Path(root) / file
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                            # Category is the folder name (studies/papers)
                            category = path.parent.name if path.parent.name != "processed" else "general"

                            file_id = data.get("nct_id") or data.get("id") or path.stem
                            title = data.get("official_title") or data.get("title") or "Untitled Document"

                            all_files.append({
                                "id": file_id,
                                "title": title,
                                "category": category,
                                "path": str(path)
                            })
                    except Exception as e:
                        print(f"Error reading {path}: {e}")
                        continue

    return {"files": all_files}
