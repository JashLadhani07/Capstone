
import asyncio
import json
import re
import time

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState, SignalOutput
from tools.search_tools import search_studies_by_meaning
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "pattern_finder_agent"
SIGNAL_TYPE = "cross_study_pattern"

_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)

RELEVANT_FIELDS = [
    "nct_id",
    "title",
    "brief_title",
    "official_title",
    "sponsor",
    "lead_sponsor",
    "condition",
    "conditions",
    "intervention",
    "interventions",
    "drug",
    "phase",
    "study_type",
    "status",
    "overall_status",
    "primary_outcome",
    "primary_outcomes",
    "results_posted",
    "completion_date",
    "enrollment",
    "enrollment_count",
]


def _compact_study(study: dict) -> dict:
    if not isinstance(study, dict):
        return {"record": str(study)[:1000]}

    metadata = study.get("metadata", {})
    if isinstance(metadata, dict):
        study = {**metadata, **study}

    compact = {
        key: study[key]
        for key in RELEVANT_FIELDS
        if key in study and study[key] not in (None, "", [])
    }

    if not compact:
        compact = {
            key: str(value)[:300]
            for key, value in list(study.items())[:10]
            if key != "metadata"
        }

    return compact


async def pattern_finder_node(state: MosaicState) -> dict:
    start_time = time.perf_counter()
    logger.info(f"{AGENT_NAME} | Starting")

    try:
        task = state.get(
            "task",
            "Find meaningful cross-study clinical trial patterns."
        )

        search_query = (
            "Clinical trials comparing drugs, sponsors, conditions, "
            "study phases, primary outcomes, enrollment, and results. "
            "Identify relationships and repeated patterns across studies. "
            + task
        )

        if state.get("nct_ids"):
            search_query += " Study IDs: " + ", ".join(state["nct_ids"])

        result = await search_studies_by_meaning.ainvoke({
            "query": search_query,
            "top_k": 20
        })

        data = json.loads(result) if isinstance(result, str) else result

        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(data["error"])

        studies = (
            data.get("results", [])
            if isinstance(data, dict)
            else data
        )

        if not isinstance(studies, list):
            raise ValueError("Unexpected study search result format.")

        compact_studies = [
            _compact_study(study)
            for study in studies[:20]
        ]

        logger.info(
            f"{AGENT_NAME} | Studies retrieved={len(compact_studies)}"
        )

        if len(compact_studies) < 3:
            elapsed = time.perf_counter() - start_time

            logger.info(
                f"{AGENT_NAME} | Insufficient studies | "
                f"time={elapsed:.2f}s"
            )

            return {
                "signals": [],
                "agents_activated": [AGENT_NAME]
            }

        system_prompt = """
You are MOSAIC's Pattern Finder Agent.

Identify meaningful patterns across multiple clinical trials.

Look for:
- Repeated missing-results patterns involving the same sponsor.
- The same drug tested by multiple sponsors or for multiple conditions.
- Repeated outcome or protocol changes across studies.
- Multiple studies showing similar compliance concerns.
- Other meaningful cross-study relationships.

STRICT RULES:
- Use ONLY the supplied study records.
- A meaningful pattern must involve at least 3 distinct studies.
- Cite the NCT IDs supporting every pattern.
- Do not invent sponsor, drug, condition, or outcome relationships.
- Similarity alone does not prove misconduct.
- Do not describe ordinary research activity as suspicious.
- Return no signal if the evidence is insufficient.

Return ONLY valid JSON:

{
  "signals": [
    {
      "nct_id": "PATTERN",
      "signal_type": "cross_study_pattern",
      "summary": "Brief description of the pattern",
      "evidence": [
        "NCT00000001: supporting fact",
        "NCT00000002: supporting fact",
        "NCT00000003: supporting fact"
      ],
      "confidence": 0.80
    }
  ]
}

If no supported patterns exist:
{"signals": []}
"""

        human_message = json.dumps({
            "task": task,
            "studies": compact_studies
        }, default=str)

        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(response.content)

        elapsed = time.perf_counter() - start_time

        logger.info(
            f"{AGENT_NAME} | Complete | "
            f"studies={len(compact_studies)} | "
            f"signals={len(signals_found)} | time={elapsed:.2f}s"
        )

        return {
            "signals": signals_found,
            "agents_activated": [AGENT_NAME]
        }

    except Exception as e:
        elapsed = time.perf_counter() - start_time

        logger.error(
            f"{AGENT_NAME} | Error | {e} | time={elapsed:.2f}s"
        )

        return {
            "error_log": [f"{AGENT_NAME}: {str(e)}"],
            "agents_activated": [AGENT_NAME]
        }


def _parse_signals(response_text: str) -> list[SignalOutput]:
    if not response_text:
        return []

    try:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                cleaned
            )

        data = json.loads(cleaned)
        signals = []

        for item in data.get("signals", []):
            if item.get("signal_type") != SIGNAL_TYPE:
                continue

            signals.append({
                "agent": AGENT_NAME,
                "signal_type": SIGNAL_TYPE,
                "nct_id": item.get("nct_id", "PATTERN"),
                "summary": item.get("summary", ""),
                "evidence": item.get("evidence", []),
                "confidence": float(item.get("confidence", 0.5))
            })

        return signals

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Signal parsing failed | {e}")
        return []


async def test_agent():
    test_state = {
        "task": (
            "Find cross-study patterns involving repeated sponsor "
            "compliance issues, missing results, drugs, and conditions."
        ),
        "nct_ids": [],
        "signals": [],
        "agents_activated": [],
        "error_log": []
    }

    start = time.perf_counter()

    print("\nRunning Pattern Finder Agent...\n")

    result = await pattern_finder_node(test_state)

    elapsed = time.perf_counter() - start

    print("\n========== AGENT OUTPUT ==========")
    print(json.dumps(result, indent=2, default=str))
    print("==================================")
    print(f"\nTotal execution time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(test_agent())
