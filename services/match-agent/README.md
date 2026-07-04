# Match-Agent — LangGraph agentic RAG

Explainable CV↔job matching microservice. Stateless FastAPI + LangGraph.

## Graph

```
retrieve (pgvector ANN, jina-embeddings-v3)
  → grade (LLM scoring vs candidate profile, OpenRouter/Qwen3)
  → explain (skills-graph: CV∩job overlap + corpus co-occurrence edges)
  → report (ranked hybrid results)
```

## API

- `GET /health`
- `POST /match` — `{"query": "optional free text", "top_k": 8}`; empty query = match against full CV profile.

Response per match: `similarity` (cosine), `llm_score` (0–100), `llm_reason`,
`skill_overlap`, `graph_edges` (co-occurring skills with weights).

## Env (all injected, nothing hardcoded)

`DATABASE_URL`, `OPENROUTER_API_KEY`, `JINA_API_KEY`, `CV_PROFILE`, `CV_SKILLS`,
optional `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` (tracing auto-enables).

## Deploy

Service `match-agent` in the n8n-automation docker-compose, internal network only
(n8n calls `http://match-agent:8100/match`), host access via `127.0.0.1:8100`.
