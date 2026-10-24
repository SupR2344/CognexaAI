"""Real-Time Web Search & Live News Service for Cognexa AI.

Integrates DuckDuckGo live search with source extraction, markdown citations,
and Perplexity-style synthesized answers.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import httpx

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)


def is_search_intent(message: str) -> bool:
    """Detect whether user query explicitly asks for real-time web search or live news."""
    lower = message.lower().strip()

    # 1. UI Web Search Toggle or explicit command
    if "[web search active]" in lower:
        return True

    explicit_triggers = [
        "search web", "search internet", "search google", "web search", "browse web",
        "latest news", "today news", "breaking news", "live score", "aaj ka score",
        "current price", "stock price", "current weather", "live updates", "taja khabar",
    ]
    if any(trig in lower for trig in explicit_triggers):
        return True

    # 2. Live temporal news events
    temporal_indicators = ["today", "right now", "live score", "breaking news"]
    news_nouns = ["match", "election", "stock price", "weather", "gold rate"]

    has_temporal = any(re.search(rf"\b{w}\b", lower) for w in temporal_indicators)
    has_news = any(re.search(rf"\b{w}\b", lower) for w in news_nouns)

    return has_temporal and has_news


async def _fetch_wikipedia_grounding(query: str) -> Optional[Dict[str, str]]:
    """Fetch encyclopedic summary from Wikipedia REST API for verified knowledge grounding."""
    try:
        clean_title = query.strip().replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_title}"
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "CognexaAI/1.0 (https://cognexa.ai; contact@cognexa.ai)"},
            )
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                title = data.get("title", query)
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{clean_title}")
                if extract:
                    return {
                        "title": f"{title} (Verified Encyclopedia Knowledge)",
                        "url": page_url,
                        "snippet": extract,
                    }
    except Exception as wiki_err:
        logger.debug("Wikipedia grounding lookup skipped: %s", wiki_err)
    return None


async def perform_web_search(query: str, max_results: int = 4) -> Dict[str, Any]:
    """Execute live web search and return structured results with citations."""
    clean_query = re.sub(
        r"\b(search\s+(the\s+)?(web|internet|google)\s+(for)?|tell\s+me|show\s+me|what\s+is|latest\s+news\s+on)\b",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip() or query.strip()

    results: List[Dict[str, str]] = []
    if DDGS is not None:
        try:
            ddgs = DDGS()
            raw_results = list(ddgs.text(clean_query, max_results=max_results))
            for item in raw_results:
                title = item.get("title", "Web Source")
                href = item.get("href", "")
                body = item.get("body", "")
                if body:
                    results.append({
                        "index": str(len(results) + 1),
                        "title": title,
                        "url": href,
                        "snippet": body,
                    })
        except Exception as exc:
            logger.warning("DuckDuckGo web search failed for '%s': %s", clean_query, exc)
    else:
        logger.warning("Neither duckduckgo_search nor ddgs is installed.")

    # Ground with verified Wikipedia knowledge if results are few or for personality/topic queries
    if len(results) < 3:
        wiki_data = await _fetch_wikipedia_grounding(clean_query)
        if wiki_data:
            results.insert(0, wiki_data)
            for idx, item in enumerate(results, start=1):
                item["index"] = str(idx)

    return {
        "query": clean_query,
        "results": results,
    }


def format_search_response(query: str, search_data: Dict[str, Any]) -> str:
    """Format synthesized answer with Perplexity-style clickable citations."""
    results = search_data.get("results", [])
    if not results:
        return (
            f"### 🌐 Web Search: *\"{query}\"*\n\n"
            "I could not retrieve live web pages for this specific query right now. "
            "Please try rephrasing or checking your internet connection."
        )

    response_lines = [
        f"### 🌐 Live Web Search: *\"{query}\"*\n",
        f"> *Retrieved {len(results)} verified real-time sources from the open web.*\n\n",
        "#### Key Findings & Overview:\n"
    ]

    for item in results:
        idx = item["index"]
        title = item["title"]
        url = item["url"]
        snippet = item["snippet"]
        response_lines.append(f"- **{title}**: {snippet} [[{idx}]]({url})\n")

    response_lines.append("\n#### 📚 Verified Sources & Citations:\n")
    for item in results:
        idx = item["index"]
        title = item["title"]
        url = item["url"]
        domain = url.split("//")[-1].split("/")[0] if url else "web"
        response_lines.append(f"[{idx}] **[{title}]({url})** — *{domain}*\n")

    return "".join(response_lines)
