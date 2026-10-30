
import asyncio
import json
import re
import time

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState, SignalOutput
from tools.search_tools import get_low_credibility_sponsors
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "track_record_agent"
SIGNAL_TYPE = "low_credibility"

_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)


async def track_record_node(state: MosaicState) -> dict:
    start_time = time.perf_counter()
    logger.info(f"{AGENT_NAME} | Starting")

    try:
        result = await get_low_credibility_sponsors.ainvoke({
            "threshold": 0.6,
            "min_studies": 3
        })

        sponsors = (
            json.loads(result) if isinstance(result, str) else result
        )

        if isinstance(sponsors, dict) and sponsors.get("error"):
            raise RuntimeError(sponsors["error"])

        if isinstance(sponsors, dict):
            sponsors = sponsors.get("sponsors", [])

        if not isinstance(sponsors, list):
            raise ValueError("Unexpected sponsor data format.")

        # Keep context small.
        sponsors = sponsors[:20]

        if not sponsors:
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"{AGENT_NAME} | No low credibility sponsors | "
                f"time={elapsed:.2f}s"
            )

            return {
                "signals": [],
                "agents_activated": [AGENT_NAME]
            }

        system_prompt = """
You are MOSAIC's Track Record Agent.

Evaluate sponsor credibility using ONLY the supplied sponsor records.

Identify sponsors with repeated patterns of poor clinical trial
reporting or research integrity concerns.

Rules:
- Do not invent sponsor history or statistics.
- Do not treat a low score alone as proof of misconduct.
- Consider study count and the available evidence.
- Generate signals only when the supplied data supports a
  meaningful pattern.
- Do not generate duplicate signals for the same sponsor.
- Use confidence that reflects the quality of the evidence.

Return ONLY valid JSON:

{
  "signals": [
    {
      "nct_id": "N/A",
      "signal_type": "low_credibility",
      "summary": "Sponsor name and explanation of the pattern",
      "evidence": ["Supporting fact 1", "Supporting fact 2"],
      "confidence": 0.85
    }
  ]
}

If no supported patterns are found:
{"signals": []}
"""

        human_message = json.dumps({
            "task": state.get(
                "task",
                "Evaluate sponsor credibility and historical patterns."
            ),
            "sponsor_records": sponsors
        }, default=str)

        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(response.content)

        elapsed = time.perf_counter() - start_time

        logger.info(
            f"{AGENT_NAME} | Complete | "
            f"sponsors={len(sponsors)} | "
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
                "nct_id": item.get("nct_id", "N/A"),
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
        "task": "Evaluate sponsor credibility and identify repeated "
                "patterns of poor clinical trial reporting.",
        "signals": [],
        "agents_activated": [],
        "error_log": []
    }

    start = time.perf_counter()

    print("\nRunning Track Record Agent...\n")

    result = await track_record_node(test_state)

    elapsed = time.perf_counter() - start

    print("\n========== AGENT OUTPUT ==========")
    print(json.dumps(result, indent=2, default=str))
    print("==================================")
    print(f"\nTotal execution time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(test_agent())
