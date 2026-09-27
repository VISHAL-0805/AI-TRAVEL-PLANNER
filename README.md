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


## Example API Requests and Responses

### Example 1:

### 1. Create a Plan

**Request:**

```bash

curl -X 'POST' \
  'http://127.0.0.1:8000/plan' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '{
  "destination": "bali",
  "start_date": "2026-09-28",
  "end_date": "2026-10-01",
  "budget_min": 1000,
  "budget_max": 4000,
  "interests": ["food", "culture", "beaches", "night life"],
  "num_travelers": 3
}'
```

**Response:**

```json
{
  "plan_id": "e5902432-f4ff-4a07-9872-ae7a8fc18e93",
  "status": "researching",
  "message": "Travel plan created. Research is starting. Poll GET /plan/{id} for status."
}
```

### 2. Check Plan Status

**Request:**

```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/plan/e5902432-f4ff-4a07-9872-ae7a8fc18e93' \
  -H 'accept: */*'
```

**Response (draft ready):**

```json
{
  "plan_id": "e5902432-f4ff-4a07-9872-ae7a8fc18e93",
  "status": "approved",
  "request": {
    "destination": "bali",
    "start_date": "2026-09-28",
    "end_date": "2026-10-01",
    "budget_min": 1000,
    "budget_max": 4000,
    "interests": [
      "food",
      "culture",
      "beaches",
      "night life"
    ],
    "num_travelers": 3
  },
  "draft_plan": {
    "raw_plan": "{\n \"trip_title\": \"Bali Culture, Cuisine & Coast 3‑Day Escape\",\n \"destination\": \"Bali\",\n \"currency\": \"IDR\",\n \"dates\": {\n \"start\": \"2026-09-28\",\n \"end\": \"2026-10-01\"\n },\n \"total_budget\": \"Rp39,250,000 (~$2,500 USD)\",\n \"daily_itinerary\": [\n {\n \"day\": 1,\n \"date\": \"2026-09-28\",\n \"theme\": \"Cultural Immersion & Local Flavors\",\n \"area\": \"Ubud\",\n \"morning\": {\n \"activity\": \"Local Food Market Tour (Ubud Market)\",\n \"time\": \"9:00 AM - 12:00 PM\",\n \"cost\": \"Rp2,590,500 (~$165 USD)\",\n \"duration\": \"3 hrs\",\n \"travel_from_previous\": \"10 min walk from hotel\"\n },\n \"afternoon\": {\n \"activity\": \"Temple / Landmark Tour (Tirta Empul & Goa Gajah)\",\n \"time\": \"1:30 PM - 4:30 PM\",\n \"cost\": \"Included in morning activity cost\",\n \"duration\": \"3 hrs\",\n \"travel_from_previous\": \"20 min taxi\"\n },\n \"evening\": {\n \"activity\": \"Dinner at Warung Babi Guling\",\n \"time\": \"6:30 PM - 8:30 PM\",\n \"cost\": \"Rp1,570,624 (~$100 USD)\",\n \"duration\": \"2 hrs\",\n \"travel_from",
    "currency": "IDR",
    "currency_symbol": "Rp",
    "exchange_rate": 15700
  },
  "research_data": {
    "destination": "bali",
    "summary": "- Is Bali Safe? The Ultimate Guide To Visiting Bali In Safety: Pickpockets operate at all times of the day. Try not in a different place. Try not to pat your pocket to check if your wallet is still there. Leave the glitzy ...\n- Bali travel safety tips and precautions: & phones close. Road Safety: Adhere to speed limits, ensure your vehicle is legally rented, avoid driving under the influence, and wear a ...\n- Is Bali Safe? An Honest Safety Guide for Tourists in 2026: Is Bali safe for tourists in 2026? An honest guide covering petty crime, scams, traffic & the safest areas including why Sanur stands apart.\n- Is Bali Safe? 2026 Safety Tips and Advice Guide: Pickpocketing can also happen in crowded bars or restaurants. How to Stay Safe: Let your phones and bags be on the inner side of the road. Do not leave ...\n- Don't Make THIS Mistake in BALI | Scams, Safety, Traffic: I'm sharing real, practical tips most tourists don't know, things that will save you time, money, and stress. Scams, Safety, Traffic. Bali's ...",
    "dates": {
      "start": "2026-09-28",
      "end": "2026-10-01"
    }
  },
  "message": "Plan finalized. Retrieve it at GET /plan/{id}/final"
}
```


### 3. Submit Review

**Approve:**

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/plan/e5902432-f4ff-4a07-9872-ae7a8fc18e93/review' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '{
  "action": "approve"
 
}'
```

**Modify:**

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/plan/e5902432-f4ff-4a07-9872-ae7a8fc18e93/review' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '{
  "action": "modify",
  "feedback": "add more street food options in day 2 evening and night"
 
}'
```

**Reject:**

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/plan/e5902432-f4ff-4a07-9872-ae7a8fc18e93/review' \
  -H 'accept: */*' \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "feedback": "Focus more on nature and hiking, less on museums"
  }'
```

**Response:**

```json
{
  "detail": "Plan is in 'PlanStatus.APPROVED' state, not ready for review"
}
```

### 4. Get Final Plan

**Request:**

```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/plan/e5902432-f4ff-4a07-9872-ae7a8fc18e93/final' \
  -H 'accept: */*'
```

**Response:**

```json
{
  "plan_id": "e5902432-f4ff-4a07-9872-ae7a8fc18e93",
  "final_plan": {
    "raw_plan": "{\n \"trip_title\": \"Bali Culture, Cuisine & Coast 3‑Day Escape\",\n \"destination\": \"Bali\",\n \"currency\": \"IDR\",\n \"dates\": {\n \"start\": \"2026-09-28\",\n \"end\": \"2026-10-01\"\n },\n \"total_budget\": \"Rp39,250,000 (~$2,500 USD)\",\n \"daily_itinerary\": [\n {\n \"day\": 1,\n \"date\": \"2026-09-28\",\n \"theme\": \"Cultural Immersion & Local Flavors\",\n \"area\": \"Ubud\",\n \"morning\": {\n \"activity\": \"Local Food Market Tour (Ubud Market)\",\n \"time\": \"9:00 AM - 12:00 PM\",\n \"cost\": \"Rp2,590,500 (~$165 USD)\",\n \"duration\": \"3 hrs\",\n \"travel_from_previous\": \"10 min walk from hotel\"\n },\n \"afternoon\": {\n \"activity\": \"Temple / Landmark Tour (Tirta Empul & Goa Gajah)\",\n \"time\": \"1:30 PM - 4:30 PM\",\n \"cost\": \"Included in morning activity cost\",\n \"duration\": \"3 hrs\",\n \"travel_from_previous\": \"20 min taxi\"\n },\n \"evening\": {\n \"activity\": \"Dinner at Warung Babi Guling\",\n \"time\": \"6:30 PM - 8:30 PM\",\n \"cost\": \"Rp1,570,624 (~$100 USD)\",\n \"duration\": \"2 hrs\",\n \"travel_from",
    "currency": "IDR",
    "currency_symbol": "Rp",
    "exchange_rate": 15700,
    "status": "approved",
    "plan_id": "e5902432-f4ff-4a07-9872-ae7a8fc18e93"
  },
  "request": {
    "destination": "bali",
    "start_date": "2026-09-28",
    "end_date": "2026-10-01",
    "budget_min": 1000,
    "budget_max": 4000,
    "interests": [
      "food",
      "culture",
      "beaches",
      "night life"
    ],
    "num_travelers": 3
  }
}
```


## Setup

### Prerequisites

- Python 3.13
- API keys for Groq, Serper, and OpenWeatherMap

### Installation

```bash
git clone https://github.com/VISHAL-0805/AI-TRAVEL-PLANNER
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

The OpenWeatherMap key is optional - the weather tool falls back to estimated data without it.

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


## Design Decisions and Tradeoffs

- **LangGraph over a simple chain:** I used LangGraph's StateGraph instead of a linear LangChain chain because the HITL requirement needs the workflow to pause, branch, and loop. StateGraph makes this natural -- approve goes to finalize, modify loops to planning, reject loops all the way back to research. A simple chain can't do conditional routing like this.

- **Two separate agents instead of one:** Splitting research and planning into separate agents keeps each prompt focused. The research agent only gathers information, and the planner only builds itineraries. This makes the prompts shorter and the outputs more reliable compared to asking one agent to do everything.

- **interrupt() for HITL:** LangGraph's `interrupt()` was the cleanest way to pause the graph mid-execution. Combined with `MemorySaver`, the full graph state is preserved while waiting for user input, and `Command(resume=...)` picks up right where it left off.

- **In-memory state store:** I used a simple dictionary with a threading lock instead of a database. For a take-home assignment this keeps setup simple -- no database to configure or migrate. The tradeoff is that all plans are lost on server restart.

- **Groq free tier:** I chose Groq because it offers free API access with fast inference. The tradeoff is limited model selection -- I'm using whichever model is available on the free tier, which may produce less consistent output than GPT-4 or Claude.

- **Static currency map:** Exchange rates are hardcoded rather than fetched from a live API. This avoids an extra API dependency and keeps things predictable, but the rates will drift over time.

- **asyncio.create_task for background work:** FastAPI's `BackgroundTasks` didn't work well with the async LangGraph workflow, so I switched to `asyncio.create_task()`. This runs the workflow in the same event loop as the API server, which is fine for a single-user demo but wouldn't scale to many concurrent plans.


## What I Would Improve With More Time

- **Persistent storage:** Replace the in-memory store with PostgreSQL or Redis so plans survive server restarts and support multiple server instances.

- **Real-time exchange rates:** Integrate a currency API (like exchangerate-api or Open Exchange Rates) instead of the static map, so budget calculations use current rates.

- **Authentication:** Add user accounts so plans are tied to specific users and not accessible by anyone who has the plan ID.

- **Streaming responses:** Use Server-Sent Events or WebSockets to stream the agent's progress to the frontend in real time instead of polling every 3 seconds.

- **Better error recovery:** If the LLM returns malformed JSON or an empty plan, the system should retry automatically instead of showing blank data to the user.

- **Caching research results:** If multiple users plan trips to the same destination in a short window, the research step could reuse cached results instead of making duplicate API calls.

- **Rate limiting:** Add request throttling to prevent abuse of the LLM and search API quotas.

- **Testing:** Add unit tests for the tools and integration tests for the full workflow. Right now there are no automated tests.

### Assumptions

- Users provide budget in USD and the system converts to local currency for display.
- The Serper API is used for web search as required by the assignment spec.
- One plan is processed at a time per server instance. Concurrent plan generation is possible but not stress-tested.
- The weather fallback provides reasonable estimates when no OpenWeatherMap key is provided.


## Notes

- Plan state is stored in memory. Restarting the server clears all plans.
- The LLM model used is configurable through `langchain-groq`. The current setup uses a free-tier model available on Groq.
- The activity recommendation tool uses a built-in database of generic activities categorized by interest type. The LLM combines these with its research findings to build destination-specific suggestions.
- Text output from the LLM goes through a cleanup function that fixes common formatting issues (missing spaces, stuck punctuation) while preserving currency strings.
