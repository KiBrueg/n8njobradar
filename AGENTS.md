# JobRadar — Codex Agent Instructions

Job-search intelligence layer: n8n workflows, PostgreSQL, LLM-based parsing, Telegram notifications.

## Stack
- **n8n** self-hosted on VPS (<VPS_IP>), pinned `n8nio/n8n:2.23.4`
- **LLM**: OpenRouter / Qwen3 (`qwen/qwen3-30b-a3b-instruct-2507`), strip `<think>` blocks before parsing
- **DB**: PostgreSQL container `n8n-automation-postgres-1`, user=hub, db=jobradar
- **n8n MCP**: available via `n8n-mcp` server — use it to read/update workflows directly

## Key files
| File | Purpose |
|------|---------|
| `spec/prompt-context.md` | JSON contract + LLM briefing |
| `spec/prompt-system.txt` | System prompt for parser |
| `spec/job-json-schema.json` | JSON Schema (draft-07) |
| `db/schema.sql` | Postgres DDL |
| `n8n/flows.md` | Workflow designs |
| `docs/job-radar-architecture.md` | Architecture overview |

## Rules
- NEVER commit directly to `main` — use feature branches (`feat/`, `fix/`, `chore/`)
- Parameterized queries only — no SQL string interpolation
- No PII in logs, no hardcoded secrets
- After any API update to a scheduled workflow: deactivate → activate (n8n scheduler bug)
- n8n API import: only `name/nodes/connections/settings`; credentials only via UI
- Strip `<think>` blocks from LLM output before JSON parse

## Flows (12 active)
| Flow | ID | Schedule |
|------|----|----------|
| 1 — Gmail | JRXuonKppWpNM3UB | 07:00 |
| 1b — IMAP | crCYiC5LUCvCyeIQ | 07:15 |
| 2 — Scraper | 8nSk6jvOSNofvLBu | 04:00 |
| 4 — Job APIs | HDJIQgfBv2Coa4jo | 04:00 |
| 5 — Digest | OBRTlQagNmknkluY | 07:00 |
| 7 — Gewerbe | VBfS8H71yz0ArkWT | 04:30 |
| 8 — Telegram | gk0F6o6f4AXCVXvF | on command |
| 11 — Auto Apply | HYl9hkFY8afKt3sb | DEACTIVATED |

## Credentials (n8n IDs)
- Postgres API: `PydDr6zKDsM95qWO`
- Telegram: `GbCUJcypvKpeqReQ`
- Gmail: `7rf7G4mjBXt01V7T`
