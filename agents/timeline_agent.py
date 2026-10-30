
import asyncio
import json
from datetime import datetime, timezone

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import MosaicState
from tools.clinical_tools import (
    fetch_study_details,
    check_results_posted,
    get_study_amendments,
)
from config.settings import settings
from config.logging_config import setup_logging

logger = setup_logging(__name__)

AGENT_NAME = "timeline_agent"
SIGNAL_TYPE = "timeline_delay"

MIN_DELAY_DAYS = 180
CONFIDENCE_THRESHOLD = 0.55


_llm = ChatGroq(
    model=settings.groq_chat_model,
    temperature=0,
    max_tokens=500,
    api_key=settings.groq_api_key,
)


async def _call_tool(tool, args):
    try:
        result = await tool.ainvoke(args)

        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"raw_response": result}

        return result

    except Exception as e:
        return {"error": str(e)}


async def _get_trial_evidence(nct_id: str):
    filing, results, amendments = await asyncio.gather(
        _call_tool(fetch_study_details, {"nct_id": nct_id}),
        _call_tool(check_results_posted, {"nct_id": nct_id}),
        _call_tool(get_study_amendments, {"nct_id": nct_id})
    )

    return {
        "nct_id": nct_id,
        "official_filing": filing,
        "results_check": results,
        "amendment_history": amendments
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
        logger.warning("Could not parse Timeline Agent response")
        return []


async def timeline_node(state: MosaicState) -> dict:
    logger.info(f"{AGENT_NAME} | Starting")

    try:
        nct_ids = state.get("nct_ids", [])

        if not nct_ids:
            logger.info("No NCT IDs supplied; skipping timeline analysis")

            return {
                "signals": [],
                "agents_activated": [AGENT_NAME]
            }

        evidence_results = await asyncio.gather(
            *[_get_trial_evidence(nct_id) for nct_id in nct_ids]
        )

        current_date = datetime.now(timezone.utc).date().isoformat()

        logger.info(
            f"{AGENT_NAME} | Studies checked={len(evidence_results)}"
        )

        system_prompt = f"""
You are the Timeline Analyst Agent for MOSAIC.

MISSION:
Identify clinical trials significantly delayed beyond their
official completion dates without a documented explanation.

CURRENT DATE:
{current_date}

MINIMUM DELAY:
{MIN_DELAY_DAYS} days past the completion date.

EVIDENCE TO EXAMINE:
1. Official trial completion date.
2. Current recruitment or completion status.
3. Whether results have been posted.
4. Amendment history and documented completion-date extensions.

REASONING RULES:

- A delay is not automatically misconduct.
- A documented extension is generally an explained delay.
- Check amendment history before identifying a delay as silent.
- If amendment history is unavailable or incomplete, mark the
  explanation as uncertain. Do not claim no amendment exists.
- Do not flag trials that have not passed their completion date.
- Account for legitimate COVID-related disruptions where supported
  by the evidence.
- Do not invent dates, amendments, or explanations.
- A missing results posting can support concern but does not alone
  prove an unexplained delay.

CONFIDENCE SCORING:

0.90-1.00: More than 2 years overdue, no documented extension,
           strong supporting evidence.
0.75-0.89: 1-2 years overdue, no documented extension.
0.60-0.74: 6-12 months overdue, no documented extension.
0.55-0.59: Plausible delay concern, but some evidence is uncertain.

Only generate signals with confidence >= {CONFIDENCE_THRESHOLD}.

OUTPUT:
Return ONLY valid JSON:

{{
  "signals": [
    {{
      "nct_id": "NCT12345678",
      "summary": "Description of the unexplained delay",
      "evidence": [
        "Official completion date",
        "Current date and calculated delay",
        "Amendment history findings",
        "Results posting status"
      ],
      "confidence": 0.70
    }}
  ]
}}

If no qualifying delays are identified:
{{"signals": []}}
"""

        human_message = f"""
TASK: {state.get("task", "Find unexplained clinical trial delays")}

TRIAL EVIDENCE:

{json.dumps(evidence_results, default=str)}

Analyze every supplied study and identify potential unexplained delays.
"""

        response = await _llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message)
        ])

        signals_found = _parse_signals(response.content)

        logger.info(
            f"{AGENT_NAME} | Complete | "
            f"studies={len(evidence_results)} | "
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
    print("\nRunning Timeline Agent...\n")

    result = await timeline_node({
        "task": "Identify trials with unexplained completion delays",
        "nct_ids": ["NCT06330519"],
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
