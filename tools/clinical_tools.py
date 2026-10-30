
import json
from datetime import datetime

from langchain_core.tools import tool

from ingestion.clinical_trials_client import ClinicalTrialsClient
from ingestion.document_parser import DocumentParser
from config.logging_config import setup_logging

logger = setup_logging(__name__)
_parser = DocumentParser()


@tool
async def fetch_study_details(nct_id: str) -> str:
    """Fetch the latest complete clinical trial record from ClinicalTrials.gov."""

    logger.info(f"Tool called: fetch_study_details | nct_id={nct_id}")

    try:
        async with ClinicalTrialsClient() as client:
            raw_study = await client.fetch_study(nct_id=nct_id)

        if raw_study is None:
            return json.dumps({
                "found": False,
                "nct_id": nct_id,
                "message": f"Study {nct_id} was not found."
            })

        parsed = _parser.parse_study(raw=raw_study)

        if parsed is None:
            return json.dumps({
                "found": False,
                "nct_id": nct_id,
                "message": "Study could not be parsed."
            })

        study = parsed.model_dump()
        study.pop("raw_data", None)

        return json.dumps({
            "found": True,
            "nct_id": nct_id,
            "study": study
        }, default=str)

    except Exception as e:
        logger.error(f"fetch_study_details failed | nct_id={nct_id} | error={e}")
        return json.dumps({
            "found": False,
            "nct_id": nct_id,
            "error": str(e)
        })


@tool
async def search_studies_by_condition(
    condition: str,
    max_results: int = 10,
    status_filter: str = "COMPLETED"
) -> str:
    """Search ClinicalTrials.gov for studies matching a medical condition."""

    logger.info(
        f"Tool called: search_studies_by_condition | condition={condition}"
    )

    try:
        async with ClinicalTrialsClient() as client:
            raw_studies = await client.search_studies(
                condition=condition,
                status=[status_filter] if status_filter else None,
                max_results=min(max_results, 50)
            )

        if not raw_studies:
            return json.dumps({
                "studies": [],
                "count": 0,
                "message": f"No studies found for {condition}."
            })

        parsed_studies = _parser.parse_studies(
            raw_studies=raw_studies
        )

        studies = []

        for study in parsed_studies:
            study_dict = study.model_dump()
            study_dict.pop("raw_data", None)
            study_dict.pop("protocol_amendments", None)
            studies.append(study_dict)

        return json.dumps({
            "studies": studies,
            "count": len(studies),
            "condition": condition,
            "status_filter": status_filter
        }, default=str)

    except Exception as e:
        logger.error(
            f"search_studies_by_condition failed | condition={condition} | error={e}"
        )
        return json.dumps({
            "error": str(e),
            "studies": [],
            "count": 0
        })


@tool
async def check_results_posted(nct_id: str) -> str:
    """Check whether a clinical trial has posted results on ClinicalTrials.gov."""

    logger.info(f"Tool called: check_results_posted | nct_id={nct_id}")

    try:
        async with ClinicalTrialsClient() as client:
            raw_study = await client.fetch_study(nct_id=nct_id)

        if raw_study is None:
            return json.dumps({
                "nct_id": nct_id,
                "found": False,
                "message": "Study not found."
            })

        parsed = _parser.parse_study(raw=raw_study)

        if parsed is None:
            return json.dumps({
                "nct_id": nct_id,
                "found": False,
                "message": "Could not parse study."
            })

        result = {
            "nct_id": parsed.nct_id,
            "found": True,
            "results_posted": parsed.results_posted,
            "status": parsed.status,
            "completion_date": parsed.completion_date,
            "sponsor": parsed.sponsor
        }

        if not parsed.results_posted and parsed.status == "COMPLETED":
            if parsed.completion_date:
                try:
                    completion = datetime.strptime(
                        parsed.completion_date[:7],
                        "%Y-%m"
                    )

                    now = datetime.utcnow()

                    months_since = (
                        (now.year - completion.year) * 12
                        + now.month - completion.month
                    )

                    months_overdue = months_since - 12

                    if months_overdue > 0:
                        result["months_overdue"] = months_overdue
                        result["years_overdue"] = round(
                            months_overdue / 12, 1
                        )
                        result["is_violation"] = True

                except ValueError:
                    pass

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error(
            f"check_results_posted failed | nct_id={nct_id} | error={e}"
        )
        return json.dumps({
            "nct_id": nct_id,
            "found": False,
            "error": str(e)
        })


@tool
async def get_study_amendments(nct_id: str) -> str:
    """Fetch protocol amendment history for a clinical trial."""

    logger.info(f"Tool called: get_study_amendments | nct_id={nct_id}")

    try:
        async with ClinicalTrialsClient() as client:
            raw_study = await client.fetch_study(nct_id=nct_id)

        if raw_study is None:
            return json.dumps({
                "nct_id": nct_id,
                "found": False,
                "amendments": []
            })

        parsed = _parser.parse_study(raw=raw_study)

        if parsed is None:
            return json.dumps({
                "nct_id": nct_id,
                "found": False,
                "amendments": []
            })

        return json.dumps({
            "nct_id": parsed.nct_id,
            "found": True,
            "title": parsed.title,
            "sponsor": parsed.sponsor,
            "start_date": parsed.start_date,
            "completion_date": parsed.completion_date,
            "primary_outcome": parsed.primary_outcome,
            "amendments": parsed.protocol_amendments,
            "amendment_count": len(parsed.protocol_amendments)
        }, default=str)

    except Exception as e:
        logger.error(
            f"get_study_amendments failed | nct_id={nct_id} | error={e}"
        )
        return json.dumps({
            "nct_id": nct_id,
            "found": False,
            "error": str(e),
            "amendments": []
        })


ALL_CLINICAL_TOOLS = [
    fetch_study_details,
    search_studies_by_condition,
    check_results_posted,
    get_study_amendments
]
