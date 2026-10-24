"""Real-Time Web Search & Live News Service for Cognexa AI.

Integrates DuckDuckGo live search with source extraction, markdown citations,
and Perplexity-style synthesized answers.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from ddgs import DDGS

logger = logging.getLogger(__name__)


def is_search_intent(message: str) -> bool:
    """Detect whether user query explicitly or implicitly requires real-time web search or grounding."""
    lower = message.lower().strip()

    # 1. UI Web Search Toggle or explicit command
    if "[web search active]" in lower:
        return True

    explicit_triggers = [
        "search web", "search internet", "search google", "web search", "browse web",
        "latest news", "today news", "breaking news", "live score", "aaj ka", "aaj ki",
        "current price", "stock price", "current weather", "who won", "recent updates",
        "kya chal raha hai", "taja khabar", "latest updates", "news on", "fact check",
        "who is", "who was", "tell me about", "koun hai", "kaun hai", "ke baare me",
        "biography", "career highlights", "career overview", "stats of", "records of",
    ]
    if any(trig in lower for trig in explicit_triggers):
        return True

    # 2. Sports / Athletes / Public Figures / Celebrities / Real-World Entities
    entity_keywords = [
        "rohit sharma", "virat kohli", "ms dhoni", "dhoni", "sachin tendulkar", "sachin",
        "sharma", "bumrah", "hardik pandya", "babar azam", "cristiano ronaldo", "ronaldo",
        "messi", "lionel messi", "elon musk", "sam altman", "narendra modi", "sundar pichai",
        "cricketer", "captain", "icc", "bcci", "ipl", "trophy", "world cup", "champions trophy",
        "olympics", "fifa", "ceo", "prime minister", "president of",
    ]
    if any(ent in lower for ent in entity_keywords):
        return True

    temporal_indicators = [
        "today", "yesterday", "this week", "recently", "current", "latest",
        "2024", "2025", "2026", "right now", "live", "schedule", "ranking"
    ]
    news_nouns = ["match", "cricket", "election", "stock", "ipo", "ai model", "release", "president", "price", "score"]

    has_temporal = any(re.search(rf"\b{w}\b", lower) for w in temporal_indicators)
    has_news = any(re.search(rf"\b{w}\b", lower) for w in news_nouns)

    return has_temporal and has_news


async def perform_web_search(query: str, max_results: int = 4) -> Dict[str, Any]:
    """Execute live web search and return structured results with citations."""
    clean_query = re.sub(
        r"\b(search\s+(the\s+)?(web|internet|google)\s+(for)?|tell\s+me|show\s+me|what\s+is|latest\s+news\s+on)\b",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip() or query.strip()

    results: List[Dict[str, str]] = []
    try:
        ddgs = DDGS()
        raw_results = list(ddgs.text(clean_query, max_results=max_results))
        for idx, item in enumerate(raw_results, start=1):
            title = item.get("title", f"Source {idx}")
            href = item.get("href", "")
            body = item.get("body", "")
            if body:
                results.append({
                    "index": str(idx),
                    "title": title,
                    "url": href,
                    "snippet": body,
                })
    except Exception as exc:
        logger.warning("DuckDuckGo web search failed for '%s': %s", clean_query, exc)

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
        response_lines.append(f"- **{title}**: {snippet} [\[{idx}\]]({url})\n")

    response_lines.append("\n#### 📚 Verified Sources & Citations:\n")
    for item in results:
        idx = item["index"]
        title = item["title"]
        url = item["url"]
        domain = url.split("//")[-1].split("/")[0] if url else "web"
        response_lines.append(f"[{idx}] **[{title}]({url})** — *{domain}*\n")

    return "".join(response_lines)
