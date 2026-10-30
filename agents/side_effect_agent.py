
import asyncio
import json

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState
from tools.clinical_tools import fetch_study_details
from tools.pubmed_tools import compare_filing_vs_papers
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "side_effect_agent"
SIGNAL_TYPE = "safety_gap"
CONFIDENCE_THRESHOLD = 0.55


_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)


def _run_pubmed_tool(args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return compare_filing_vs_papers.invoke(args)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _get_trial_evidence(nct_id: str):
    try:
        filing = await fetch_study_details.ainvoke({
            "nct_id": nct_id
        })

        if isinstance(filing, str):
            try:
                filing = json.loads(filing)
            except json.JSONDecodeError:
                filing = {"raw_response": filing}

        filing_summary = json.dumps(filing, default=str)

        pubmed_result = await asyncio.to_thread(
            _run_pubmed_tool,
            {
                "nct_id": nct_id,
                "filing_summary": filing_summary
            }
        )

        if isinstance(pubmed_result, str):
            pubmed_result = json.loads(pubmed_result)

        return {
            "nct_id": nct_id,
            "filing": filing,
            "papers": pubmed_result.get("papers", []),
            "papers_count": pubmed_result.get("papers_count", 0),
            "has_papers": pubmed_result.get("has_papers", False),
            "error": pubmed_result.get("error")
        }

    except Exception as e:
        logger.error(
            f"Evidence retrieval failed | nct_id={nct_id} | error={e}"
        )

        return {
            "nct_id": nct_id,
            "error": str(e)
        }


def _parse_signals(response_text: str):
    if not response_text:
        return []

    try:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        data = json.loads(cleaned)

        signals = []

        for item in data.get("signals", []):
            confidence = float(item.get("confidence", 0))

            if (
                item.get("nct_id")
                and confidence >= CONFIDENCE_THRESHOLD
            ):
                signals.append({
                    "agent": AGENT_NAME,
                    "signal_type": SIGNAL_TYPE,
                    "nct_id": item["nct_id"],
                    "summary": item.get("summary", ""),
                    "evidence": item.get("evidence", []),
                    "confidence": confidence
                })

        return signals

    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Could not parse Side Effect Agent response")
        return []


async def side_effect_node(state: MosaicState) -> dict:
    logger.info(f"{AGENT_NAME} | Starting")

    try:
        nct_ids = state.get("nct_ids", [])

        if not nct_ids:
            logger.info("No NCT IDs supplied; skipping safety comparison")

            return {
                "signals": [],
                "agents_activated": [AGENT_NAME]
            }

        evidence_results = await asyncio.gather(
            *[_get_trial_evidence(nct_id) for nct_id in nct_ids]
        )

        usable_evidence = [
            result for result in evidence_results
            if not result.get("error") and result.get("has_papers")
        ]

        logger.info(
            f"{AGENT_NAME} | Evidence retrieved="
            f"{len(usable_evidence)}/{len(nct_ids)}"
        )

        if not usable_evidence:
            logger.info("No usable filing-paper comparisons available")

            return {
                "signals": [],
                "agents_activated": [AGENT_NAME]
            }

        system_prompt = """
You are the Side Effect Checker Agent for MOSAIC.

Your task is to identify potential safety discrepancies between
official clinical trial filings and published research papers.

Compare the two sources carefully.

LOOK FOR:
1. Serious adverse events in papers that are absent from filings.
2. Different severity descriptions for the same adverse event.
3. Deaths, hospitalisations or treatment discontinuations
   reported in papers but not reflected in the filing.
4. Safety findings that materially contradict official claims.

IMPORTANT RULES:
- Only use the supplied evidence.
- Compare the same trial and relevant patient population.
- Do not assume that an event absent from an abstract was absent
  from the full paper or official filing.
- Distinguish additional detail from an actual contradiction.
- A paper and filing may use different terminology without disagreeing.
- Do not infer sponsor misconduct or intentional concealment.
- If evidence is incomplete, explain the uncertainty.
- Borderline but plausible discrepancies should be flagged
  for human review rather than automatically dismissed.

CONFIDENCE:
0.90-1.00: Explicit and strong contradiction.
0.75-0.89: Clear discrepancy supported by both sources.
0.60-0.74: Plausible discrepancy with some missing detail.
0.55-0.59: Borderline concern requiring human review.

Only generate signals with confidence >= 0.55.

Return ONLY valid JSON in this format:

{
  "signals": [
    {
      "nct_id": "NCT12345678",
      "summary": "Description of the potential safety discrepancy",
      "evidence": [
        "What the official filing reports",
        "What the published paper reports",
        "Why these findings may disagree"
      ],
      "confidence": 0.65
    }
  ]
}

If no potential discrepancies are found, return:
{"signals": []}
"""

        human_message = f"""
TASK: {state.get("task", "Identify safety gaps")}

OFFICIAL FILINGS AND PUBLISHED PAPER EVIDENCE:

{json.dumps(usable_evidence, default=str)}

Compare the evidence and identify potential safety discrepancies.
Prioritise patient safety while maintaining evidence-based reasoning.
"""

        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(response.content)

        logger.info(
            f"{AGENT_NAME} | Complete | "
            f"studies={len(usable_evidence)} | "
            f"signals={len(signals_found)}"
        )

        return {
            "signals": signals_found,
            "agents_activated": [AGENT_NAME]
        }

    except Exception as e:
        logger.error(f"{AGENT_NAME} | Error | {e}")

        return {
            "error_log": [f"{AGENT_NAME}: {str(e)}"],
            "agents_activated": [AGENT_NAME]
        }


async def test_agent():
    print("\nRunning Side Effect Agent...\n")

    result = await side_effect_node({
        "task": "Identify potential discrepancies in trial safety reporting",
        "nct_ids": ["NCT04356937"],
        "signals": [],
        "agents_activated": [],
        "error_log": []
    })

    print("\n========== AGENT OUTPUT ==========")
    print(json.dumps(result, indent=2))
    print("==================================")

    return result


if __name__ == "__main__":
    asyncio.run(test_agent())
