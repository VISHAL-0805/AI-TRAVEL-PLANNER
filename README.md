# AI Travel Planner

A multi-agent travel planning system built with LangGraph and FastAPI. It uses two specialized AI agents
 1. a research agent
 2. a planner agent
that work together to generate detailed, day-by-day travel itineraries. The system includes a human-in-the-loop approval step so users can review, modify, or reject plans before they are finalized.


## How It Works

The system follows a graph-based workflow with four main stages:

1. **Research** - The research agent searches the web (via Serper API) and checks weather forecasts (via OpenWeatherMap) to gather destination info like top attractions, safety tips, local customs, and transportation options.

2. **Planning** - The planner agent takes the research output, allocates the budget across categories (accommodation, food, activities, transport, misc), and builds a structured day-by-day itinerary with timed activities, meal suggestions, and cost estimates -- all in the destination's local currency.

3. **Human Review** - The workflow pauses using LangGraph's `interrupt()` mechanism. The user can approve the plan, request modifications, or reject it entirely and trigger a re-research cycle.

4. **Finalization** - Once approved, the plan is saved and available for download.


## Architecture

```
app/
  main.py              - FastAPI application and API endpoints
  models.py            - Pydantic request/response schemas
  agents/
    research.py        - Research agent (web search + weather tools)
    planner.py         - Planner agent (budget + activity tools)
  core/
    graph.py           - LangGraph StateGraph workflow definition
    state.py           - Thread-safe in-memory plan store
    config.py          - Environment variable loading
    utils.py           - Currency conversion and text cleanup utilities
  tools/
    web_search.py      - Serper API integration for web search
    weather.py         - OpenWeatherMap forecast with mock fallback
    budget.py          - Budget allocation across spending categories
    activities.py      - Activity recommendation engine
ui.py                  - Streamlit frontend
requirements.txt
.env                   - API keys (not committed)
```


## Tech Stack

- **LangGraph** - Orchestrates the multi-agent workflow as a StateGraph. Uses `MemorySaver` as the checkpointer so state persists across the human-in-the-loop pause.
- **LangChain + Groq** - LLM calls go through `langchain-groq` using a free-tier model. Each agent has its own tools bound via `bind_tools()`.
- **FastAPI** - REST API with four endpoints for creating plans, checking status, submitting reviews, and retrieving the final plan.
- **Streamlit** - Interactive frontend where users fill in trip details, watch progress, review the draft, and download the final itinerary.
- **Serper API** - Powers the web search tool so the research agent can pull real-time destination info from Google.
- **OpenWeatherMap** - Provides weather forecasts. Falls back to estimated data if no API key is set.


## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/plan` | Submit a new travel plan request |
| GET | `/plan/{plan_id}` | Check plan status and get draft when ready |
| POST | `/plan/{plan_id}/review` | Submit review (approve / modify / reject) |
| GET | `/plan/{plan_id}/final` | Retrieve the finalized plan |


## Setup

### Prerequisites

- Python 3.13
- API keys for Groq, Serper, and OpenWeatherMap

### Installation

```bash
git clone <repo-url>
cd assignment
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key
SERPER_API_KEY=your_serper_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
```

The OpenWeatherMap key is optional -- the weather tool falls back to estimated data without it.

### Running

Start the FastAPI backend:

```bash
uvicorn app.main:app --reload
```

In a separate terminal, start the Streamlit frontend:

```bash
streamlit run ui.py
```

The API docs are available at `http://127.0.0.1:8000/docs` (Swagger UI).
The Streamlit UI runs at `http://localhost:8501`.


## How the HITL Flow Works

LangGraph's `interrupt()` function pauses the workflow at the human review node. The graph state is saved by the `MemorySaver` checkpointer, so the process can be resumed later when the user submits their review through the API.

- **Approve** - The workflow moves to the finalize node and saves the plan.
- **Modify** - The workflow loops back to the planning node with the user's feedback, so the planner agent regenerates the itinerary.
- **Reject** - The workflow loops all the way back to the research node, re-researching the destination with the user's feedback taken into account.

This is handled through LangGraph's `Command(resume=...)` which passes the review data back into the paused graph.


## Budget and Currency Handling

All costs are displayed in the destination's local currency with a USD equivalent shown in parentheses. The system maps 50+ destinations to their currency codes and approximate exchange rates. Budget is split into five categories:

- Accommodation: 35%
- Food: 25%
- Activities: 20%
- Local transport: 12%
- Miscellaneous: 8%

The planner agent uses the `allocate_budget` tool to calculate these splits and passes the breakdown to the LLM so it can assign realistic costs to each activity in the itinerary.


## Notes

- Plan state is stored in memory. Restarting the server clears all plans.
- The LLM model used is configurable through `langchain-groq`. The current setup uses a free-tier model available on Groq.
- The activity recommendation tool uses a built-in database of generic activities categorized by interest type. The LLM combines these with its research findings to build destination-specific suggestions.
- Text output from the LLM goes through a cleanup function that fixes common formatting issues (missing spaces, stuck punctuation) while preserving currency strings.
