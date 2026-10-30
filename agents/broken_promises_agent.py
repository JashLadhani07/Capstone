
import asyncio
import json
import re
import time

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState, SignalOutput
from tools.clinical_tools import get_study_amendments
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "broken_promises_agent"
SIGNAL_TYPE = "broken_promise"

_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)


async def broken_promises_node(state: MosaicState) -> dict:
    start_time = time.perf_counter()
    logger.info(f"{AGENT_NAME} | Starting")

    try:
        nct_ids = state.get("nct_ids", [])

        if not nct_ids:
            raise ValueError("No NCT IDs provided.")

        results = await asyncio.gather(
            *[
                get_study_amendments.ainvoke({"nct_id": nct_id})
                for nct_id in nct_ids
            ],
            return_exceptions=True
        )

        evidence = []

        for nct_id, result in zip(nct_ids, results):
            if isinstance(result, Exception):
                evidence.append({
                    "nct_id": nct_id,
                    "error": str(result)
                })
                continue

            try:
                data = json.loads(result) if isinstance(result, str) else result

                evidence.append({
                    "nct_id": nct_id,
                    "amendment_history": data
                })

            except (json.JSONDecodeError, TypeError):
                evidence.append({
                    "nct_id": nct_id,
                    "amendment_history": str(result)
                })

        system_prompt = """
You are MOSAIC's Broken Promises Agent.

Your task is to detect potential primary outcome switching in clinical trials.

Analyze ONLY the supplied protocol amendment evidence.

A potential signal requires evidence that:
1. The originally registered primary outcome is identifiable.
2. The primary outcome was subsequently changed.
3. The change occurred after participant enrollment began.

Do not flag:
- Administrative amendments.
- Changes to secondary outcomes alone.
- Changes made before enrollment began.
- Amendments without evidence of an actual primary outcome change.

Do not assume that outcome switching automatically proves fraud.
Do not invent dates, outcomes, or explanations.
If evidence is incomplete or ambiguous, return no signal.

Return ONLY valid JSON:

{
  "signals": [
    {
      "nct_id": "NCT00000000",
      "signal_type": "broken_promise",
      "summary": "Brief explanation of the outcome change",
      "evidence": [
        "Originally registered primary outcome: X",
        "Changed primary outcome: Y",
        "Change occurred after enrollment began"
      ],
      "confidence": 0.85
    }
  ]
}

If no supported cases are found:
{"signals": []}
"""

        human_message = json.dumps({
            "task": state.get(
                "task",
                "Identify primary outcome switching."
            ),
            "amendment_evidence": evidence
        }, default=str)

        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(response.content)

        elapsed = time.perf_counter() - start_time

        logger.info(
            f"{AGENT_NAME} | Complete | "
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
                "nct_id": item.get("nct_id", ""),
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
        "task": "Check for primary outcome switching after enrollment began.",
        "nct_ids": ["NCT04356937"],
        "signals": [],
        "agents_activated": [],
        "error_log": []
    }

    start = time.perf_counter()

    print("\nRunning Broken Promises Agent...\n")

    result = await broken_promises_node(test_state)

    elapsed = time.perf_counter() - start

    print("\n========== AGENT OUTPUT ==========")
    print(json.dumps(result, indent=2, default=str))
    print("==================================")
    print(f"\nTotal execution time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(test_agent())
