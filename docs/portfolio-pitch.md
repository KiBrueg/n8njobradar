# JobRadar — AI-Powered Job Search Automation

## Kurzfassung (TL;DR)

Ich habe ein vollständig automatisiertes Job-Tracking-System gebaut, das eingehende Bewerbungsemails, Jobbörsen und Karriereseiten mit KI verarbeitet, alle relevanten Daten strukturiert speichert und automatisch Kalendereinträge sowie Echtzeit-Benachrichtigungen erstellt — alles ohne manuellen Aufwand.

---

## Problem

Wer aktiv auf Jobsuche ist, verliert schnell den Überblick:
- Dutzende Emails pro Woche (Einladungen, Absagen, HR-Nachrichten, Jobbörsen-Updates)
- Keine zentrale Übersicht über den Status jeder Bewerbung
- Interview-Termine landen nicht automatisch im Kalender
- Manuelle Nachverfolgung kostet täglich 30–60 Minuten

---

## Lösung

**JobRadar** ist ein selbst entwickeltes Automatisierungssystem auf Basis von n8n (self-hosted auf VPS), das alle jobrelated Signale aus verschiedenen Quellen erfasst, mit einem LLM klassifiziert und in einer strukturierten Datenbank speichert.

### Datenquellen
| Quelle | Technologie |
|--------|-------------|
| Gmail (Hauptpostfach) | Gmail API via OAuth2 |
| mail.de (Zweitpostfach) | IMAP |
| Jobbörsen-APIs | Arbeitnow, Remotive, RemoteOK, Jobicy, Himalayas |
| Karriereseiten | Firecrawl Web Scraper |
| Manuelle Eingabe | n8n Webhook / Form |

---

## Architektur

```
Trigger (Gmail / IMAP / API / Scraper)
  → Normalize (einheitliches JSON-Format)
  → Security Checks (Sender-Risiko + Prompt-Injection-Erkennung)
  → LLM Call (OpenRouter / Qwen3) — klassifiziert + extrahiert
  → Parse & Validate
  → Postgres Write (idempotent upsert)
  → Side Effects (parallel):
       ├── Google Calendar Event
       ├── Telegram Alert (priority=high)
       └── Gmail Label (automatische Sortierung)
```

Alle Flows laufen täglich um 04:00 Uhr CET. Daily Digest wird um 07:00 Uhr gesendet.

---

## KI-Integration

Das Herzstück ist ein **Custom System Prompt** (~22.000 Zeichen), der dem LLM beibringt:
- Kategorie zu erkennen (Einladung, Angebot, Absage, Test-Task, Newsletter...)
- Alle relevanten Felder zu extrahieren (Unternehmen, Position, Gehalt, Technologien, Deadlines)
- Priorität zu bewerten (1–100 Relevanz-Score)
- Prompt-Injection-Versuche aus Emails zu erkennen und zu melden

Das LLM gibt immer ein stabiles, validiertes JSON zurück — n8n schreibt es direkt in die DB.

---

## Sicherheit

Da Emails aus unbekannten Quellen kommen, habe ich zwei Sicherheitslayer eingebaut:

**1. Sender Risk Check** (vor dem LLM-Call):
- Klassifiziert Absender-Domain als `low / medium / high`
- Erkennt: Typosquatting (Levenshtein-Distanz), disposable Domains, IP-Adressen als Domain, Scam-Keywords
- High-risk Emails werden gestoppt und nicht ans LLM weitergegeben

**2. Hard Injection Check**:
- Regex-basierte Erkennung von 17 Injection-Patterns
- Erkennt: "Ignore previous instructions", system-prompt-Leaks, ADMIN:-Prefixes etc.
- Emails mit erkannten Patterns werden verworfen

Zusätzlich: Parameterized Queries only, keine PII in Logs, Secrets nur via `$env.*`.

---

## Datenmodell (Postgres)

```
companies       — deduplizierte Firmendatenbank (tenant-aware)
employers       — HR-Kontakte, verknüpft mit companies
jobs            — eine Zeile pro Stelle (upsert on conflict)
job_events      — vollständiges Audit-Log jedes Signals
schema_versions — Migrationsverlauf
```

Multi-tenant-ready durch `tenant_id` auf allen Tabellen. Idempotente Upserts — sicher für Retries.

---

## Ergebnis / Output

- **Google Calendar**: Alle Interviews als Events, alle anderen Vorgänge als Tagesübersicht `[JobRadar] YYYY-MM-DD`
- **Telegram**: Sofort-Alert bei Angeboten und High-Priority-Einladungen mit Link zum Original-Email
- **Gmail Labels**: Automatische Sortierung in `job/interview`, `job/offer`, `job/rejected`, `job/active` etc.
- **Daily Digest** (07:00): TOP-5 Vorgänge nach Relevanz, gruppiert in drei Tiers (🔥 ≥80 / ⭐ 50–79 / 📋 <50)

---

## Tech Stack

| Komponente | Technologie |
|------------|-------------|
| Orchestrierung | n8n (self-hosted, Docker Compose, Hetzner VPS) |
| KI / LLM | OpenRouter API — Qwen3-30B |
| Datenbank | PostgreSQL |
| Email (Push) | Gmail API (OAuth2) |
| Email (Pull) | IMAP (mail.de) |
| Web Scraping | Firecrawl API |
| Notifications | Telegram Bot API |
| Kalender | Google Calendar API |
| Versionierung | Git + GitHub |

---

## Was mich als Kandidaten auszeichnet

Dieses Projekt ist kein Tutorial-Klon — es löst ein echtes persönliches Problem mit produktionsreifem Code:

- **Eigeninitiative**: Idee, Architektur, Implementierung und Debugging komplett selbst
- **Sicherheitsbewusstsein**: Sender-Risikoanalyse und Injection-Schutz in einem privaten Tool — weil es die richtige Herangehensweise ist
- **Skalierbarkeit**: Multi-tenant-Schema, Stateless LLM-Parser, Connection Pooling — kann für ein Unternehmen oder SaaS adaptiert werden
- **Dokumentation**: Vollständige Deployment-Doku, Security-Checkliste, JSON-Schema mit Validation
- **Pragmatismus**: Bekannte Constraints (PowerShell Unicode-Bugs, n8n API-Einschränkungen) identifiziert, dokumentiert und umgangen

---

## Was ich für Ihr HR-Team tun kann

Dieselbe Logik, die ich für meine eigene Jobsuche gebaut habe, lässt sich direkt auf HR-Prozesse übertragen — mit erheblichem Zeitgewinn.

### Konkrete Anwendungsfälle

**Bewerbungseingang automatisieren**
Eingehende Bewerbungen per Email werden automatisch klassifiziert, relevante Felder extrahiert (Position, Erfahrung, Technologien, Standort) und ins ATS oder eine interne Datenbank geschrieben — ohne manuelle Vorsortierung. Realistische Zeitersparnis: 2–4 Stunden pro Woche pro Recruiter.

**Interview-Koordination ohne hin-und-her**
Sobald ein Kandidat eine Zusage schickt, legt das System automatisch einen Kalendertermin an, schickt Bestätigungen an beide Seiten und erstellt eine Zusammenfassung im internen Tool. Was heute 5–10 Emails kostet, wird zu einem einzigen automatischen Ablauf.

**Screening-Vorfilterung mit LLM**
Ein trainiertes Prompt-System prüft eingehende Bewerbungen gegen ein Anforderungsprofil und gibt einen strukturierten Score-Report aus — keine Entscheidung, aber eine fundierte Priorisierungsgrundlage für den Recruiter. Zeit bis zum ersten Screening-Anruf sinkt messbar.

**Statusupdates ohne Aufwand**
Kandidaten erhalten automatische Statusbenachrichtigungen in definierten Prozessschritten (Eingang bestätigt → Screening → Interview → Entscheidung) — konsistent, zeitnah, ohne dass jemand manuell schreibt.

**Reporting und Analytics**
Alle Daten landen in einer strukturierten Datenbank. Dashboards zeigen: Time-to-hire, Absagequoten nach Quelle, Trichter-Analyse — ohne Excel, ohne manuelles Zusammenführen.

### Warum ich das umsetzen kann

Ich habe nicht nur ein Konzept — ich habe die gesamte Pipeline allein gebaut, debuggt und produktiv betrieben. Ich kenne die typischen Fallstricke (API-Limits, Unicode-Bugs, LLM-Halluzinationen, Sicherheitslücken durch unstrukturierte Inputs) und weiß wie man damit umgeht. Neue Automatisierungen für Ihr Team wären keine Experimente, sondern wiederholbare, dokumentierte Prozesse.

> **Repository**: github.com/[username]/n8njobradar  
> **Live Demo**: auf Anfrage (n8n-Instanz läuft produktiv)
