import json
import logging
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from app.tools.budget import allocate_budget
from app.tools.activities import recommend_activities
from app.core.config import GROQ_API_KEY
from app.core.utils import get_currency_info, clean_plan_dict

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT_TEMPLATE = """You are a travel itinerary planner. Using the destination research provided,
create a detailed day-by-day travel itinerary.

RULES:
1. Show ALL costs in CURRENCY_PLACEHOLDER (the destination's local currency). Add USD equivalent in parentheses.
   Example: "cost": "¥5,225 (~$35 USD)"
2. Group activities by geographic area each day — minimize backtracking.
   Name the neighborhood/area for each day's theme.
3. Include specific timing for each activity (e.g., "9:00 AM - 11:00 AM").
4. Add travel time between activities (e.g., "10 min walk" or "20 min by subway").
5. Keep descriptions clear with proper spacing. Under 20 words each.

Use the allocate_budget tool first, then recommend_activities.

IMPORTANT: Return ONLY valid JSON, no extra text.
{
    "trip_title": "...",
    "destination": "...",
    "currency": "CURRENCY_PLACEHOLDER",
    "dates": {"start": "...", "end": "..."},
    "total_budget": "BUDGET_PLACEHOLDER",
    "daily_itinerary": [
        {
            "day": 1,
            "date": "...",
            "theme": "...",
            "area": "neighborhood name for the day",
            "morning": {
                "activity": "...",
                "time": "9:00 AM - 11:00 AM",
                "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)",
                "duration": "2 hrs",
                "travel_from_previous": "10 min walk from hotel"
            },
            "afternoon": {
                "activity": "...",
                "time": "12:00 PM - 3:00 PM",
                "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)",
                "duration": "3 hrs",
                "travel_from_previous": "5 min walk"
            },
            "evening": {
                "activity": "...",
                "time": "6:00 PM - 8:00 PM",
                "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)",
                "duration": "2 hrs",
                "travel_from_previous": "15 min by subway"
            },
            "meals": {
                "breakfast": {"suggestion": "...", "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)"},
                "lunch": {"suggestion": "...", "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)"},
                "dinner": {"suggestion": "...", "cost": "0 CURRENCY_PLACEHOLDER (~$0 USD)"}
            },
            "daily_total": "0 CURRENCY_PLACEHOLDER (~$0 USD)"
        }
    ],
    "accommodation": {"type": "...", "area": "...", "nightly_rate": "0 CURRENCY_PLACEHOLDER (~$0 USD)"},
    "packing_tips": ["..."],
    "important_notes": ["..."]
}"""


def create_planner_agent():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.4,
    )
    tools = [allocate_budget, recommend_activities]
    return llm.bind_tools(tools), tools


async def run_planner(request_data: dict, research_data: dict) -> dict:
    llm_with_tools, tools = create_planner_agent()
    tool_map = {t.name: t for t in tools}

    start = datetime.strptime(request_data["start_date"], "%Y-%m-%d")
    end = datetime.strptime(request_data["end_date"], "%Y-%m-%d")
    num_days = max((end - start).days, 1)
    avg_budget = (request_data["budget_min"] + request_data["budget_max"]) / 2

    currency_code, exchange_rate, currency_symbol = get_currency_info(request_data["destination"])
    total_budget_local = f"{currency_symbol}{round(avg_budget * exchange_rate):,}"

    budget_str = f"{total_budget_local} (~${int(avg_budget)} USD)"
    prompt = PLANNER_SYSTEM_PROMPT_TEMPLATE.replace("CURRENCY_PLACEHOLDER", currency_code).replace("BUDGET_PLACEHOLDER", budget_str)

    user_msg = (
        f"Create a {num_days}-day itinerary based on this research:\n\n"
        f"{research_data.get('summary', 'No research available.')}\n\n"
        f"Trip details:\n"
        f"- Destination: {request_data['destination']}\n"
        f"- Dates: {request_data['start_date']} to {request_data['end_date']} ({num_days} days)\n"
        f"- Budget: ${request_data['budget_min']} - ${request_data['budget_max']} USD "
        f"({total_budget_local} {currency_code} at target ${int(avg_budget)} USD)\n"
        f"- Local currency: {currency_code} (1 USD = {exchange_rate} {currency_code})\n"
        f"- Interests: {', '.join(request_data.get('interests', ['general']))}\n"
        f"- Travelers: {request_data.get('num_travelers', 1)}\n\n"
        f"First use allocate_budget to plan spending, then recommend_activities to find things to do. "
        f"Then build the full day-by-day itinerary with all costs in {currency_code}."
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_msg),
    ]

    for _ in range(6):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                result = await tool_fn.ainvoke(tc["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    final_content = messages[-1].content if messages else "{}"
    logger.info(f"Planner raw output length: {len(final_content)}")
    logger.info(f"Planner raw output (first 500 chars): {final_content[:500]}")

    plan = _parse_plan_json(final_content)
    plan = clean_plan_dict(plan)
    plan["currency"] = currency_code
    plan["currency_symbol"] = currency_symbol
    plan["exchange_rate"] = exchange_rate
    return plan


def _parse_plan_json(content: str) -> dict:
    start_idx = content.find("{")
    if start_idx == -1:
        return {"raw_plan": content}

    end_idx = content.rfind("}") + 1
    json_str = content[start_idx:end_idx] if end_idx > start_idx else content[start_idx:]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    fixed = json_str
    open_braces = fixed.count("{") - fixed.count("}")
    open_brackets = fixed.count("[") - fixed.count("]")
    fixed += "]" * open_brackets + "}" * open_braces

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return {"raw_plan": content}
