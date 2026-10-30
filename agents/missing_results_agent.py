
import asyncio
import json
import re
import time

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState, SignalOutput
from tools.clinical_tools import check_results_posted
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "missing_results_agent"
SIGNAL_TYPE = "missing_results"

_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)


async def missing_results_node(state: MosaicState) -> dict:
    start_time = time.perf_counter()

    logger.info(f"{AGENT_NAME} | Starting")

    try:
        nct_ids = state.get("nct_ids", [])

        if not nct_ids:
            raise ValueError(
                "No NCT IDs provided. Supply at least one study ID."
            )

        # Fetch live evidence directly without an LLM tool-selection call.
        results = await asyncio.gather(
            *[
                check_results_posted.ainvoke({"nct_id": nct_id})
                for nct_id in nct_ids
            ]
        )

        evidence = []

        for result in results:
            try:
                data = json.loads(result) if isinstance(result, str) else result

                evidence.append({
                    "nct_id": data.get("nct_id"),
                    "found": data.get("found"),
                    "results_posted": data.get("results_posted"),
                    "status": data.get("status"),
                    "completion_date": data.get("completion_date"),
                    "months_overdue": data.get("months_overdue", 0),
                    "is_violation": data.get("is_violation", False),
                    "sponsor": data.get("sponsor"),
                    "error": data.get("error")
                })

            except (json.JSONDecodeError, TypeError):
                logger.warning("Could not parse clinical tool result")

        system_prompt = """
You are MOSAIC's Missing Results Agent.

Identify completed clinical trials with overdue missing results.

Rules:
- Use ONLY the supplied evidence.
- A study is a potential violation only if:
  results_posted is false,
  status is COMPLETED,
  and months_overdue is greater than 0.
- Do not invent facts or sponsor history.
- Confidence must reflect the supplied evidence.
- Do not classify missing or invalid data as a violation.

Return ONLY valid JSON:
{
  "signals": [
    {
      "nct_id": "NCT00000000",
      "signal_type": "missing_results",
      "summary": "Brief explanation",
      "evidence": ["fact 1", "fact 2"],
      "confidence": 0.85
    }
  ]
}

If no violations are found, return:
{"signals": []}
"""

        human_message = json.dumps({
            "task": state.get(
                "task",
                "Identify trials with overdue missing results."
            ),
            "evidence": evidence
        }, default=str)

        # Exactly one LLM call for the complete analysis.
        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(
            response.content,
            AGENT_NAME
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            f"{AGENT_NAME} | Complete | "
            f"signals={len(signals_found)} | "
            f"time={elapsed:.2f}s"
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


def _parse_signals(
    response_text: str,
    agent_name: str
) -> list[SignalOutput]:

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
                "agent": agent_name,
                "signal_type": SIGNAL_TYPE,
                "nct_id": item.get("nct_id", ""),
                "summary": item.get("summary", ""),
                "evidence": item.get("evidence", []),
                "confidence": float(
                    item.get("confidence", 0.5)
                )
            })

        return signals

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Signal parsing failed | {e}")
        return []


# Run this agent independently for testing.
async def test_agent():
    test_state = {
        "task": "Check whether this trial has overdue missing results.",
        "nct_ids": ["NCT04885530","NCT06330519"],
        "signals": [],
        "agents_activated": [],
        "error_log": []
    }

    start = time.perf_counter()

    print("\nRunning Missing Results Agent...\n")

    result = await missing_results_node(test_state)

    elapsed = time.perf_counter() - start

    print("\n========== AGENT OUTPUT ==========")
    print(json.dumps(result, indent=2, default=str))
    print("==================================")
    print(f"\nTotal execution time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(test_agent())
