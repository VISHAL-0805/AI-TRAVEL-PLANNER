# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the application

Two processes must run concurrently in separate terminals:

```bash
uvicorn app.main:app --reload       # FastAPI backend on :8000
streamlit run ui.py                  # Streamlit frontend on :8501
```

The Streamlit UI calls the FastAPI API via `http://127.0.0.1:8000` (hardcoded in `ui.py`). Swagger docs are at `/docs`.

Requires a `.env` file in the project root with `GROQ_API_KEY`, `SERPER_API_KEY`, and optionally `OPENWEATHER_API_KEY` (the weather tool falls back to canned data without it).

## Architecture

### Request lifecycle

1. `POST /plan` creates a plan ID and spawns a background task via `asyncio.create_task(_run_workflow(...))`. **`BackgroundTasks` was tried first and silently hung** — do not switch back.
2. `GET /plan/{id}` is polled by the Streamlit UI every 3 seconds.
3. The workflow runs in [app/core/graph.py](app/core/graph.py) as a LangGraph `StateGraph`: `research → planning → human_review → finalize`, with conditional edges that loop `human_review` back to `research` (on reject) or `planning` (on modify).
4. At `human_review_node`, LangGraph's `interrupt()` pauses the graph. State is persisted by `MemorySaver`. `POST /plan/{id}/review` calls `graph.ainvoke(Command(resume=review_data))` to resume.

### Two state stores, intentionally separate

- **`plan_store`** ([app/core/state.py](app/core/state.py)) — thread-safe in-memory dict that the API reads/writes. This is what the UI polls.
- **LangGraph `MemorySaver`** — checkpoints the full graph state (needed for `interrupt()`/`Command(resume=...)` to work).

Both get updated by the graph nodes. The API never reads from `MemorySaver` directly; it reads `plan_store`.

### Agents

Both agents in [app/agents/](app/agents/) use `openai/gpt-oss-120b` on Groq via `langchain-groq`. They bind their tools with `llm.bind_tools()` and run a manual tool-calling loop (no LangGraph react-agent — the loops are hand-rolled for control over retries and token budgets).

- `research.py` — tools: `search_web` (Serper), `get_weather_forecast` (OpenWeatherMap). If the model emits an invalid tool call (Groq returns 400 with `tool_use_failed`), the message history is **reset** mid-loop to prevent subsequent 400s cascading. Partial research is collected across tool outputs as a fallback.
- `planner.py` — tools: `allocate_budget`, `recommend_activities`. If the tool-calling loop produces empty content, a **second LLM call with no tool bindings** is made with a direct JSON-only prompt (see `run_planner`).

### Why the planner is defensive

Groq free tier allows **8000 tokens/min total (input + output)**. Responses frequently get truncated mid-string. The planner handles this with three layers:

1. **`_parse_plan_json`** — tries strict JSON parse, then `_close_truncated_json` (walks char-by-char tracking string/escape state and bracket stack, closes open strings and brackets), then progressively trims from the end finding the largest parseable prefix.
2. **`_normalize_plan`** — the LLM uses inconsistent key names. Normalizer maps `dates.start_date → dates.start`, converts nested `total_budget: {INR: 208750, USD_equivalent: 2500}` to `"208,750 INR (~$2,500 USD)"`, handles morning/afternoon/evening as dict/list/string. See `_coerce_cost` and `_normalize_activity_block` for the full mapping.
3. **`_build_fallback_plan`** — generic template itinerary used when the LLM returns nothing. **Merged with any partial LLM output** (keeps LLM's `trip_title`/`destination`/`dates` if they exist, fills in missing `daily_itinerary` from the template).

If you touch the planner, keep all three layers. Removing any of them re-introduces blank-plan bugs.

### Currency handling

`app/core/utils.py` holds `DESTINATION_CURRENCY_MAP` (50+ cities → currency code + rate) and `CURRENCY_SYMBOLS`. All costs are shown in local currency with USD in parens. `clean_text()` protects currency patterns (like `¥5,225 (~$35 USD)`) from regex-based space-insertion cleanup by swapping them for placeholders first.

### HITL routing

`route_after_review` in `graph.py`:
- `APPROVE` → `finalize` (end)
- `MODIFY` → `planning` (regenerates itinerary with research intact)
- `REJECT` → `research` (full restart with feedback)

The planner node has `await asyncio.sleep(15)` before running — this is **intentional** to let Groq's per-minute rate limit reset between the research and planning phases. Removing it causes rate-limit cascades.

## Known constraints

- Groq free tier: 8000 tokens/min. Users should wait ~60s between plan generations. The code mitigates but cannot eliminate truncation.
- In-memory plan store — all plans lost on server restart.
- The LLM model `openai/gpt-oss-120b` occasionally emits invalid tool calls like `{"cursor": 0, "id": 0}`. The research agent handles this; if you add new tool-using agents, replicate the invalid-tool-call recovery pattern from `research.py`.
