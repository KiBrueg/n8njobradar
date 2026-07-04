"""JobRadar Match-Agent — LangGraph agentic RAG for explainable CV-job matching.

Graph: retrieve (pgvector ANN) -> grade (LLM scoring) -> explain (skills graph) -> report.
Called by n8n via HTTP; no state stored here (stateless, scales horizontally).
"""
import json
import os
import re
from typing import Any, TypedDict

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

DB_DSN = os.environ.get("DATABASE_URL") or (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    "@postgres:5432/jobradar"
)
JINA_KEY = os.environ["JINA_API_KEY"]
CV_PROFILE = os.environ.get("CV_PROFILE", "")
CV_SKILLS = [s.strip() for s in os.environ.get("CV_SKILLS", "").split(",") if s.strip()]

llm = ChatOpenAI(
    model=os.environ.get("MATCH_LLM_MODEL", "qwen/qwen3-30b-a3b-instruct-2507"),
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    temperature=0,
    max_tokens=1500,
)

# Langfuse tracing is optional: activates only when keys are present in env
callbacks: list[Any] = []
if os.environ.get("LANGFUSE_PUBLIC_KEY"):
    from langfuse.callback import CallbackHandler

    callbacks = [CallbackHandler()]


class MatchState(TypedDict, total=False):
    query: str
    top_k: int
    candidates: list[dict]
    graded: list[dict]
    report: dict


def _embed(text: str) -> list[float]:
    r = httpx.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {JINA_KEY}"},
        json={
            "model": "jina-embeddings-v3",
            "task": "retrieval.query",
            "dimensions": 1024,
            "input": [text[:8000]],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def retrieve(state: MatchState) -> MatchState:
    vec = _embed(state["query"])
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    with psycopg.connect(DB_DSN) as conn:
        rows = conn.execute(
            """
            SELECT j.id::text, j.job_title, c.name, j.location, j.job_type::text,
                   j.tech_stack, j.summary, j.source_url, j.contact_email,
                   (1 - (j.embedding <=> %s::vector))::float AS similarity
            FROM jobs j
            LEFT JOIN companies c ON c.tenant_id = j.tenant_id AND c.company_id = j.company_id
            WHERE j.embedding IS NOT NULL
              AND j.current_stage NOT IN ('rejected', 'withdrawn')
            ORDER BY j.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec_str, vec_str, state.get("top_k", 8)),
        ).fetchall()
    state["candidates"] = [
        {
            "job_id": r[0], "job_title": r[1], "company": r[2], "location": r[3],
            "job_type": r[4], "tech_stack": r[5] or [], "summary": r[6],
            "source_url": r[7], "contact_email": r[8], "similarity": round(r[9], 3),
        }
        for r in rows
    ]
    return state


GRADE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Du bewertest, wie gut Stellenanzeigen zum Kandidatenprofil passen.\n"
     "Kandidatenprofil:\n{profile}\n\n"
     "Antworte NUR mit einem JSON-Array: "
     '[{{"job_id": "...", "score": 0-100, "reason": "ein Satz"}}]. '
     "Kein Markdown, kein Text davor oder danach."),
    ("user", "{jobs}"),
])


def grade(state: MatchState) -> MatchState:
    jobs_brief = [
        {k: c[k] for k in ("job_id", "job_title", "company", "location", "job_type", "tech_stack", "summary")}
        for c in state["candidates"]
    ]
    msg = (GRADE_PROMPT | llm).invoke(
        {"profile": CV_PROFILE, "jobs": json.dumps(jobs_brief, ensure_ascii=False)},
        config={"callbacks": callbacks},
    )
    raw = re.sub(r"<think>[\s\S]*?</think>", "", msg.content).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    scores = {g["job_id"]: g for g in json.loads(raw)}
    state["graded"] = [
        {**c, "llm_score": scores.get(c["job_id"], {}).get("score"),
         "llm_reason": scores.get(c["job_id"], {}).get("reason")}
        for c in state["candidates"]
    ]
    return state


def explain(state: MatchState) -> MatchState:
    """Skills-graph explanation: CV∩job overlap + co-occurring skills across the whole corpus."""
    cv_lower = {s.lower(): s for s in CV_SKILLS}
    with psycopg.connect(DB_DSN) as conn:
        for g in state["graded"]:
            overlap = [cv_lower[t.lower()] for t in g["tech_stack"] if t.lower() in cv_lower]
            g["skill_overlap"] = overlap
            g["graph_edges"] = []
            if overlap:
                rows = conn.execute(
                    """
                    SELECT s.skill, count(*) AS weight
                    FROM jobs j, LATERAL unnest(j.tech_stack) AS s(skill)
                    WHERE j.tech_stack && %s::text[]
                      AND NOT (lower(s.skill) = ANY(%s))
                    GROUP BY s.skill ORDER BY weight DESC LIMIT 5
                    """,
                    (overlap, [o.lower() for o in overlap]),
                ).fetchall()
                g["graph_edges"] = [
                    {"from": overlap[0], "to": r[0], "co_occurrences": r[1]} for r in rows
                ]
    return state


def report(state: MatchState) -> MatchState:
    ranked = sorted(
        state["graded"],
        key=lambda g: (g.get("llm_score") or 0, g["similarity"]),
        reverse=True,
    )
    state["report"] = {
        "query": state["query"],
        "matches": ranked,
        "method": "hybrid: pgvector ANN retrieval + LLM grading + skills-graph explanation",
    }
    return state


workflow = StateGraph(MatchState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade", grade)
workflow.add_node("explain", explain)
workflow.add_node("report", report)
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade")
workflow.add_edge("grade", "explain")
workflow.add_edge("explain", "report")
workflow.add_edge("report", END)
graph = workflow.compile()

app = FastAPI(title="JobRadar Match-Agent")


class MatchRequest(BaseModel):
    query: str = ""  # empty -> match against full CV profile
    top_k: int = 8


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "graph_nodes": list(workflow.nodes.keys())}


@app.post("/match")
def match(req: MatchRequest) -> dict:
    query = req.query.strip() or CV_PROFILE
    if not query:
        raise HTTPException(400, "query empty and CV_PROFILE not configured")
    result = graph.invoke(
        {"query": query, "top_k": min(req.top_k, 20)},
        config={"callbacks": callbacks},
    )
    return result["report"]
