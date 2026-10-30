
import json
from pathlib import Path
from typing import Any

from config.logging_config import setup_logging
from ingestion.document_parser import ParsedStudy, ParsedPaper

logger = setup_logging(__name__)

# Local data directory
BASE_DIR = Path(__file__).resolve().parent.parent / "data"

PREFIX_RAW_STUDIES = BASE_DIR / "raw" / "studies"
PREFIX_RAW_PAPERS = BASE_DIR / "raw" / "papers"
PREFIX_PROCESSED_STUDIES = BASE_DIR / "processed" / "studies"
PREFIX_PROCESSED_PAPERS = BASE_DIR / "processed" / "papers"


class LocalStore:
    """
    Local replacement for the old Google Cloud Storage store.

    The class keeps the same name and methods so the rest of
    the MOSAIC code does not need major changes.
    """

    def __init__(self):
        # Create local folders
        PREFIX_RAW_STUDIES.mkdir(parents=True, exist_ok=True)
        PREFIX_RAW_PAPERS.mkdir(parents=True, exist_ok=True)
        PREFIX_PROCESSED_STUDIES.mkdir(parents=True, exist_ok=True)
        PREFIX_PROCESSED_PAPERS.mkdir(parents=True, exist_ok=True)

        logger.info(f"Local storage initialized | path={BASE_DIR}")

    async def save_raw_study(
        self,
        nct_id: str,
        data: dict[str, Any],
    ) -> str:

        path = PREFIX_RAW_STUDIES / f"{nct_id}.json"

        await self._save_json(path, data)

        logger.info(f"Saved raw study | nct_id={nct_id} | path={path}")

        return str(path)

    async def save_raw_paper(
        self,
        pmid: str,
        data: dict[str, Any],
    ) -> str:

        path = PREFIX_RAW_PAPERS / f"{pmid}.json"

        await self._save_json(path, data)

        logger.info(f"Saved raw paper | pmid={pmid} | path={path}")

        return str(path)

    async def save_parsed_study(
        self,
        study: ParsedStudy,
    ) -> str:

        path = PREFIX_PROCESSED_STUDIES / f"{study.nct_id}.json"

        await self._save_json(
            path,
            study.model_dump(),
        )

        logger.info(
            f"Saved parsed study | nct_id={study.nct_id} | path={path}"
        )

        return str(path)

    async def save_parsed_paper(
        self,
        paper: ParsedPaper,
    ) -> str:

        path = PREFIX_PROCESSED_PAPERS / f"{paper.pmid}.json"

        await self._save_json(
            path,
            paper.model_dump(),
        )

        logger.info(
            f"Saved parsed paper | pmid={paper.pmid} | path={path}"
        )

        return str(path)

    async def load_parsed_study(
        self,
        nct_id: str,
    ) -> ParsedStudy | None:

        path = PREFIX_PROCESSED_STUDIES / f"{nct_id}.json"

        data = await self._load_json(path)

        if not data:
            return None

        return ParsedStudy(**data)

    async def list_processed_studies(self) -> list[str]:

        if not PREFIX_PROCESSED_STUDIES.exists():
            return []

        nct_ids = []

        for file in PREFIX_PROCESSED_STUDIES.glob("*.json"):
            nct_ids.append(file.stem)

        logger.info(
            f"Listed processed studies | count={len(nct_ids)}"
        )

        return nct_ids

    async def _save_json(
        self,
        path: Path,
        data: dict[str, Any],
    ) -> None:

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(
            path,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                default=str,
            )

    async def _load_json(
        self,
        path: Path,
    ) -> dict[str, Any] | None:

        try:

            if not path.exists():
                logger.warning(
                    f"File not found | path={path}"
                )
                return None

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:

                return json.load(f)

        except Exception as e:

            logger.error(
                f"Failed to load JSON | path={path} | error={e}"
            )

            return None

