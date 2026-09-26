import httpx
from langchain_core.tools import tool
from app.core.config import SERPER_API_KEY


@tool
def search_web(query: str) -> str:
    """Search the web for travel-related information using Serper API.
    Use this to find attractions, local tips, safety info, cultural norms,
    and other destination-specific details."""
    if not SERPER_API_KEY:
        return "Error: SERPER_API_KEY not configured"

    resp = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": 5},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("organic", [])[:5]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        results.append(f"- {title}: {snippet}")

    if data.get("answerBox"):
        box = data["answerBox"]
        answer = box.get("answer") or box.get("snippet", "")
        if answer:
            results.insert(0, f"Quick answer: {answer}")

    return "\n".join(results) if results else "No results found."
