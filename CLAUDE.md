# JobRadar — Project Context

Job-search intelligence layer: JSON contract, LLM prompts, DB model (Postgres), n8n workflow logic.
Self-contained — deployable to any n8n instance. See `docs/deploy.md`, `.env.example`.

## Scope
Focus on: 1) JSON schema completeness, 2) prompt stability, 3) DB model correctness, 4) workflow logic (what, not how to deploy).

## Key files
| File | Purpose |
|------|---------|
| `spec/prompt-context.md` | Briefing + JSON contract |
| `spec/prompt-system.txt` | System prompt for parser |
| `spec/job-json-schema.json` | JSON Schema (draft-07) |
| `docs/job-radar-architecture.md` | Architecture overview |
| `db/schema.sql` | Postgres DDL |
| `n8n/flows.md` | Workflow designs |

## Design principles
Portfolio + small-business grade. Explicit > implicit. Idempotent (ON CONFLICT). No PII in logs. Parameterized queries only. Document the "why".

## Security checkpoints
Mid-task: no hardcoded secrets, no SQL interpolation, no PII in logs, no unsanitized input to LLM/SQL/shell.
Final: run grep for leaked keys/IPs/emails, verify `.gitignore` covers `sessions/`, `.env*`, `NEXT_SESSION.md`, `.claude/`, `outputs/`.

## Operational constraints
- **LLM:** OpenRouter / Qwen3 (`qwen/qwen3-30b-a3b-instruct-2507`). Strip `<think>` blocks before parsing.
- **n8n API import:** only `name/nodes/connections/settings`. Credentials only via UI.
- **VPS SSH:** `ssh -i "$env:USERPROFILE\.ssh\id_ed25519" <user>@<VPS_IP>` (PowerShell) / `ssh -i "$USERPROFILE/.ssh/id_ed25519"` (Bash)
- **n8n HTTP calls:** Windows PowerShell only (`Invoke-RestMethod`), curl from sandbox = 403
- **.env edits:** never `echo >>`, always `grep -v KEY > .tmp && mv && echo`
- **PowerShell 5.1:** no `&&`, use `;`

## Sources
| Source | `input_source` | Protocol |
|--------|---------------|---------|
| Gmail | `email` | Gmail API |
| mail.de | `email` | IMAP |
| Firecrawl | `scraped` | HTTP |
| Manual | `manual` | Webhook |

## Personal docs
Moved to `C:\Users\brueg\Desktop\projects\anschreiben`. Only `gas/anschreiben-generator.gs` stays here.
