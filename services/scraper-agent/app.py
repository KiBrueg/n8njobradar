"""Scraper-Agent — lightweight ScrapeGraphAI-style service.

Fetches a URL (via crawl4ai for JS support, fallback to httpx+BS4),
then asks Qwen3 to extract structured data per a user-supplied prompt.
Used as fallback when SGai Cloud API exhausts monthly credits.

Endpoints:
  GET  /health
  POST /scrape  { url, prompt, max_chars? }  →  { result, url, chars_sent }
"""
import json
import os
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
LLM_MODEL = os.environ.get("SCRAPER_LLM_MODEL", "qwen/qwen3-30b-a3b-instruct-2507")
LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_CHARS = int(os.environ.get("SCRAPER_MAX_CHARS", "6000"))
CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://crawl4ai:11235")

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

SYSTEM_PROMPT = (
    "You are a web scraping assistant. "
    "You receive cleaned webpage text and a data-extraction prompt. "
    "Extract exactly what is asked and respond ONLY with valid JSON — no markdown, no explanation. "
    "If the requested data is not found, return an empty object {}."
)

app = FastAPI(title="Scraper-Agent")


class ScrapeRequest(BaseModel):
    url: str
    prompt: str
    max_chars: int = DEFAULT_MAX_CHARS


def _fetch_via_crawl4ai(url: str, max_chars: int) -> str | None:
    """Try crawl4ai (JS-capable, playwright). Returns None if unavailable."""
    try:
        r = httpx.post(
            f"{CRAWL4AI_URL}/crawl",
            json={"urls": [url], "priority": 10, "crawler_config": {"headless": True, "page_timeout": 15000}},
            timeout=30,
        )
        r.raise_for_status()
        md = r.json()["results"][0].get("markdown") or {}
        if isinstance(md, dict):
            text = md.get("fit_markdown") or md.get("raw_markdown") or ""
        else:
            text = str(md)
        return text[:max_chars] if len(text) > 100 else None
    except Exception:
        return None


def _fetch_via_httpx(url: str, max_chars: int) -> str:
    """Plain HTTP fetch + BS4 cleanup. No JS execution."""
    try:
        r = httpx.get(url, headers=FETCH_HEADERS, timeout=15, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"upstream {e.response.status_code}: {url}")
    except httpx.RequestError as e:
        raise HTTPException(502, f"fetch failed: {e}")

    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def _fetch_text(url: str, max_chars: int) -> str:
    return _fetch_via_crawl4ai(url, max_chars) or _fetch_via_httpx(url, max_chars)


def _llm_extract(page_text: str, prompt: str) -> dict:
    body = {
        "model": LLM_MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"PAGE CONTENT:\n{page_text}\n\nEXTRACTION TASK:\n{prompt}"},
        ],
    }
    try:
        r = httpx.post(
            LLM_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"LLM error {e.response.status_code}: {e.response.text[:200]}")
    except httpx.RequestError as e:
        raise HTTPException(502, f"LLM request failed: {e}")

    raw = r.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": LLM_MODEL}


@app.post("/scrape")
def scrape(req: ScrapeRequest) -> dict:
    if not req.url.startswith("http"):
        raise HTTPException(400, "url must start with http:// or https://")
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    crawl4ai_text = _fetch_via_crawl4ai(req.url, req.max_chars)
    if crawl4ai_text:
        page_text = crawl4ai_text
        engine = "crawl4ai"
    else:
        page_text = _fetch_via_httpx(req.url, req.max_chars)
        engine = "httpx"

    result = _llm_extract(page_text, req.prompt)

    return {"result": result, "url": req.url, "chars_sent": len(page_text), "engine": engine}
