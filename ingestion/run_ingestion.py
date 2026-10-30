
import asyncio

from ingestion.clinical_trials_client import ClinicalTrialsClient
from ingestion.pubmed_client import PubMedClient
from ingestion.document_parser import DocumentParser
from ingestion.local_store import LocalStore

from memory.semantic_store import SemanticStore
from config.logging_config import setup_logging

logger = setup_logging(__name__)

SEARCH_CONDITIONS = [
    "diabetes",
    "cancer",
    "cardiovascular disease",
]

MAX_STUDIES_PER_CONDITION = 5
MAX_PAPERS_PER_STUDY = 6


async def run_ingestion():

    logger.info("=" * 60)
    logger.info("Starting MOSAIC ingestion pipeline")
    logger.info(f"Conditions: {', '.join(SEARCH_CONDITIONS)}")
    logger.info(f"Max studies per condition: {MAX_STUDIES_PER_CONDITION}")
    logger.info(f"Max papers per study: {MAX_PAPERS_PER_STUDY}")
    logger.info("=" * 60)

    parser = DocumentParser()
    store = LocalStore()
    semantic_store = SemanticStore()

    total_studies = 0
    total_papers = 0

    # Sponsor -> unique study IDs
    sponsor_studies = {}

    async with ClinicalTrialsClient() as ct_client:
        async with PubMedClient() as pubmed_client:

            for condition in SEARCH_CONDITIONS:

                logger.info(f"Fetching studies | condition={condition}")

                raw_studies = await ct_client.search_studies(
                    condition=condition,
                    max_results=MAX_STUDIES_PER_CONDITION,
                )

                logger.info(
                    f"Fetched {len(raw_studies)} studies | "
                    f"condition={condition}"
                )

                parsed_studies = parser.parse_studies(raw_studies)

                for study in parsed_studies:

                    raw_match = next(
                        (
                            r for r in raw_studies
                            if r.get("protocolSection", {})
                            .get("identificationModule", {})
                            .get("nctId") == study.nct_id
                        ),
                        None,
                    )

                    # Extract lead sponsor
                    if raw_match:
                        sponsor = (
                            raw_match
                            .get("protocolSection", {})
                            .get("sponsorCollaboratorsModule", {})
                            .get("leadSponsor", {})
                            .get("name")
                        )

                        if sponsor:
                            sponsor = sponsor.strip()

                            if sponsor:
                                sponsor_studies.setdefault(
                                    sponsor, set()
                                ).add(study.nct_id)

                        await store.save_raw_study(
                            nct_id=study.nct_id,
                            data=raw_match,
                        )

                    # Save parsed study
                    await store.save_parsed_study(study)
                    total_studies += 1

                    # Fetch related PubMed papers
                    papers = await pubmed_client.fetch_papers_for_trial(
                        nct_id=study.nct_id,
                        max_results=MAX_PAPERS_PER_STUDY,
                    )

                    parsed_papers = parser.parse_papers(papers)

                    for paper in parsed_papers:

                        await store.save_raw_paper(
                            pmid=paper.pmid,
                            data=paper.model_dump(),
                        )

                        await store.save_parsed_paper(paper)

                        total_papers += 1

    # Register sponsor profiles after ingestion
    sponsor_counts = {
        sponsor: len(study_ids)
        for sponsor, study_ids in sponsor_studies.items()
    }

    if sponsor_counts:
        await semantic_store.register_ingested_sponsors(
            sponsor_counts
        )

    logger.info("=" * 60)
    logger.info("Ingestion complete")
    logger.info(f"Studies saved: {total_studies}")
    logger.info(f"Papers saved: {total_papers}")
    logger.info(f"Sponsor profiles created/updated: {len(sponsor_counts)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_ingestion())
