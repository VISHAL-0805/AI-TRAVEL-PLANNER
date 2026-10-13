import logging

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from app.tools.web_search import search_web
from app.tools.weather import get_weather_forecast
from app.core.config import GROQ_API_KEY

logger = logging.getLogger(__name__)


RESEARCH_SYSTEM_PROMPT = """You are a travel research specialist. Your job is to gather comprehensive
destination intelligence for trip planning.

Given a travel request, research the destination thoroughly:
1. Top attractions and must-see places
2. Local tips and cultural norms
3. Safety information and things to avoid
4. Best areas to stay
5. Transportation options within the city
6. Seasonal/weather considerations
7. Food scene highlights

Use the search_web tool for up-to-date information and get_weather_forecast for climate data.
Be thorough but concise. Structure your findings clearly.

Return your research as a well-organized summary that a planner can use to build an itinerary."""


def create_research_agent():
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.3,
        max_tokens=2000,
    )
    tools = [search_web, get_weather_forecast]
    return llm.bind_tools(tools), tools


async def run_research(request_data: dict) -> dict:
    llm_with_tools, tools = create_research_agent()
    tool_map = {t.name: t for t in tools}

    destination = request_data["destination"]
    start_date = request_data["start_date"]
    end_date = request_data["end_date"]
    interests = ", ".join(request_data.get("interests", []))

    user_msg = (
        f"Research this trip:\n"
        f"Destination: {destination}\n"
        f"Dates: {start_date} to {end_date}\n"
        f"Interests: {interests or 'general sightseeing'}\n"
        f"Travelers: {request_data.get('num_travelers', 1)}\n\n"
        f"Search for top things to do, local tips, safety info, and weather."
    )

    messages = [
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    collected_research = []
    for i in range(5):
        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Research LLM call {i} failed: {e}")
            break

        messages.append(response)

        if response.content:
            collected_research.append(response.content)

        if not response.tool_calls:
            break

        bad_tool_calls = False
        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn:
                try:
                    result = await tool_fn.ainvoke(tc["args"])
                    messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                    collected_research.append(str(result)[:600])
                except Exception as e:
                    logger.warning(f"Tool {tc['name']} failed with args {tc['args']}: {e}")
                    messages.append(ToolMessage(content=f"Error: tool call had invalid arguments", tool_call_id=tc["id"]))
                    bad_tool_calls = True

        if bad_tool_calls:
            messages = [
                SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ]

    final_content = messages[-1].content if messages and hasattr(messages[-1], "content") and messages[-1].content else ""
    if not final_content and collected_research:
        final_content = "\n\n".join(collected_research[-3:])
    if not final_content:
        final_content = f"Basic research for {destination}: Popular travel destination with cultural, historical, and culinary attractions."

    return {
        "destination": destination,
        "summary": final_content,
        "dates": {"start": start_date, "end": end_date},
    }
