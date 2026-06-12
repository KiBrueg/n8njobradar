# JobRadar — KI-Komponente: Technische Beschreibung

## Aufgabe des LLM im System

Das LLM (Qwen3-30B via OpenRouter API) übernimmt ausschließlich die Rolle eines **strukturierten Parsers und Klassifizierers**. Es trifft keine Entscheidungen, schreibt keine Emails, und steuert keine Aktionen — das ist bewusste Architekturentscheidung.

n8n normalisiert alle Eingaben (Email, Scraping, manuelle Eingabe) in ein einheitliches JSON-Envelope und sendet es an das LLM. Das LLM gibt genau ein valides JSON-Objekt zurück. n8n schreibt es in die Datenbank und triggert Folgeaktionen.

Das Prinzip: **LLM als Funktion, nicht als Agent.**

---

## System Prompt — Designentscheidungen

Der System Prompt umfasst ~22.000 Zeichen und ist das Herzstück der KI-Integration. Kernprinzipien beim Aufbau:

**Explizites Output-Schema statt freier Antworten**
Das LLM bekommt ein vollständiges JSON-Schema mit allen Feldern, Typen, erlaubten Enum-Werten und Beschreibungen. Keine Interpretation, kein "antworte wie du möchtest" — jedes Feld ist definiert.

**Fehlerbehandlung eingebaut**
Felder die das LLM nicht extrahieren kann, werden `null` — nicht weggelassen, nicht geraten. Das ermöglicht zuverlässige Validierung im n8n-Code danach.

**Injection-Erkennung als LLM-Aufgabe**
Neben der Extraktion prüft das LLM ob der Input Anzeichen von Prompt-Injection enthält (`injection_suspected: boolean`). Das ist eine zweite Verteidigungslinie nach dem Regex-Check in n8n.

**Relevanz-Score als numerisches Feld**
Das LLM bewertet jede Stelle auf einer Skala 1–100 nach Übereinstimmung mit dem Ziel-Profil. Das ermöglicht Triage: Daily Digest gruppiert nach Tiers (≥80 / 50–79 / <50), ohne dass Schwellenwerte hart einprogrammiert werden müssen.

**Kategorie als primäres Klassifizierungsmerkmal**
9 Kategorien: `job_posting`, `hr_invite`, `interview_invite`, `test_task`, `offer`, `rejection`, `follow_up`, `platform_notification`, `manual_note`. Jede Kategorie triggert andere Folgeaktionen in n8n.

---

## Prompt Engineering — konkrete Techniken

| Technik | Anwendung |
|---------|-----------|
| Explicit schema | Alle Felder mit Typ, Enum, Beschreibung im Prompt |
| Negative examples | "Falls kein Datum erkennbar → `null`, nicht raten" |
| Chain reasoning | `<think>` blocks von Qwen3 werden gestript, nur JSON-Output verwendet |
| Output validation | n8n-Code-Node validiert alle Pflichtfelder, Enum-Werte, Datentypen nach LLM-Call |
| Fallback handling | Bei Parse-Error: Exception mit den ersten 300 Zeichen des LLM-Outputs für Debugging |

---

## Umgang mit Qwen3-spezifischem Verhalten

Qwen3 gibt `<think>...</think>`-Blöcke vor dem eigentlichen Output aus (Chain-of-Thought). Diese werden in der Parse-Node gestript:

```javascript
raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
```

Außerdem wird Markdown-Formatting aus dem JSON entfernt (` ```json ` Wrapper), bevor `JSON.parse()` aufgerufen wird.

---

## Sicherheit: zwei Verteidigungslinien

**Vor dem LLM-Call (n8n Code Node):**
- Sender Risk Check: Domain-Klassifizierung (Typosquatting via Levenshtein, disposable Domains, suspicious TLDs, Scam-Keywords)
- Hard Injection Check: 17 Regex-Pattern (u.a. "ignore previous instructions", `[SYSTEM]`-Tags, "reveal your prompt")
- Emails mit `sender_risk = high` oder erkannten Injections werden gestoppt — nie ans LLM weitergegeben

**Im LLM-Call selbst:**
- `injection_suspected: boolean` im Output-Schema — LLM meldet selbst erkannte Versuche
- Input wird auf 10.000 Zeichen begrenzt bevor er ans LLM geht

---

## Warum kein Fine-Tuning, kein RAG

Bewusste Entscheidung gegen Komplexität:
- **Kein Fine-Tuning**: Ein gut konstruierter System Prompt mit explizitem Schema liefert stabile Outputs ohne teures Training. Bei Änderungen am Schema reicht ein Prompt-Update.
- **Kein RAG**: Die Klassifizierung braucht kein externes Wissen — der gesamte Kontext kommt aus dem Input selbst.
- **Kein Streaming**: Das LLM-Ergebnis wird einmalig geparst. Latenz (6–8s) ist bei Background-Processing irrelevant.

---

## Skalierbarkeit der KI-Komponente

Der LLM-Parser ist vollständig **stateless** — er kennt keine vorherigen Calls, keine User-State, keine Session. Das bedeutet:
- Horizontal skalierbar ohne Anpassungen
- Einfaches A/B-Testing von Modellen (nur `model`-Parameter ändern)
- Austauschbar: OpenAI, Anthropic, Mistral — gleiche Schnittstelle via OpenRouter

---

## Messbarer Nutzen

| Metrik | Manuell | Mit JobRadar |
|--------|---------|--------------|
| Zeit bis Email klassifiziert | 2–5 Min | ~7 Sekunden |
| Interview-Termin in Kalender | Manuell | Automatisch |
| Vollständigkeit der Felder | Lückenhaft | Standardisiert |
| Audit-Log | Keiner | Vollständig in Postgres |
| Tägliche Bearbeitungszeit | 30–60 Min | ~5 Min (Digest lesen) |
