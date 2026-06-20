# WF3 — Angebot-Generator: OpenAI System Prompts

## Aufbau des Workflows

```
Trigger: HERO Watch Projects (Status → "Angebotserstellung")
      ODER: Microsoft Forms / Webhook (Kundenanfrage-Formular)
  → HERO GraphQL: Kundendaten laden
  → OpenAI: ANGEBOT-GENERIERUNG (Prompt A) → Positionen + Text
  → Word-Template: Platzhalter befüllen
  → PDF konvertieren
  → SharePoint: /Projekte/{ID}/Angebote/ speichern
  → Outlook: PDF als Anhang an Kunden senden
  → HERO: Projektstatus → "Angebot versendet"
  → Teams: Benachrichtigung an Vertrieb
```

---

## Prompt A — Angebot generieren (Make.com: System Prompt)

```
Du bist ein erfahrener Kalkulator und Sachbearbeiter in einem deutschen Handwerksbetrieb.

Deine Aufgabe ist es, auf Basis einer Kundenanfrage ein strukturiertes Angebot zu erstellen.

WICHTIG — Kalkulations-Grundlage:
- Arbeitsstunden Geselle: 55 €/Std. netto
- Arbeitsstunden Meister: 80 €/Std. netto
- Materialaufschlag: 20% auf Einkaufspreis
- Anfahrt: 0,45 €/km (beide Richtungen)
- MwSt: 19%
- Gültigkeitsdauer Angebot: 30 Tage

Erstelle:
1. ANSCHREIBEN: Formelles Anschreiben auf Deutsch (Sie-Form, DIN 5008, max. 3 Absätze)
2. POSITIONEN: Liste der Leistungspositionen als JSON-Array

Format der Positionen:
[
  {
    "pos": 1,
    "beschreibung": "Ausführliche Beschreibung der Leistung",
    "menge": Zahl,
    "einheit": "Std|Stk|m|m²|m³|pauschal",
    "einzelpreis_netto": Zahl,
    "gesamtpreis_netto": Zahl
  }
]

3. ZUSAMMENFASSUNG:
{
  "anschreiben": "vollständiger Brieftext",
  "positionen": [...],
  "gesamt_netto": Zahl,
  "mwst_betrag": Zahl,
  "gesamt_brutto": Zahl,
  "hinweis": "optionaler Hinweis für den Meister"
}

Eingabedaten:
- Kundenname: {{kundenname}}
- Firma: {{firma}}
- Adresse: {{adresse}}
- Projektbeschreibung: {{projektbeschreibung}}
- Gewerk: {{gewerk}}
- Besonderheiten: {{besonderheiten}}

Antworte AUSSCHLIESSLICH als gültiges JSON gemäß obigem Schema.
```

**Make.com Einstellungen:**
- Model: `gpt-4o`
- Temperature: `0.3`
- Response Format: JSON Object
- Max Tokens: `2000`

---

## Word-Template Platzhalter

Erstelle eine Word-Datei (`angebot-template.docx`) mit diesen Platzhaltern:

```
{{ANGEBOTSNUMMER}}        → z.B. A-2026-0547
{{DATUM}}                 → z.B. 21.06.2026
{{GUELTIG_BIS}}           → Datum + 30 Tage
{{KUNDENNAME}}            → aus HERO
{{FIRMA}}                 → aus HERO
{{STRASSE}}               → aus HERO
{{PLZ_ORT}}               → aus HERO
{{ANSCHREIBEN_TEXT}}      → aus OpenAI
{{POSITIONEN_TABELLE}}    → Schleife in Make (Iterator)
{{GESAMT_NETTO}}          → formatiert als "1.234,56 €"
{{MWST_BETRAG}}           → formatiert
{{GESAMT_BRUTTO}}         → formatiert
{{ERSTELLER_NAME}}        → aus Make-Variable (fester Wert)
{{ERSTELLER_TELEFON}}     → fest
{{ERSTELLER_EMAIL}}       → fest
```

**In Make.com:** Microsoft Word Templates Modul oder Google Docs → Export als PDF.

---

## Angebotsnummer generieren (Make.com Formula)

```
A-{{formatDate(now; "YYYY")}}-{{padStart(increment; 4; "0")}}
```

Für den Zähler: Data Store in Make.com mit `angebot_counter` Key verwenden.

---

## HERO GraphQL Query — Kundendaten laden

```graphql
query GetContact($id: ID!) {
  contacts(filter: { id: { eq: $id } }) {
    id
    first_name
    last_name
    company_name
    email
    phone_home
    phone_mobile
    addresses {
      street
      zipcode
      city
    }
  }
}
```

**Endpoint:** `https://login.hero-software.de/api/external/v7/graphql`  
**Header:** `Authorization: Bearer {{hero_api_key}}`

---

## HERO Status-Update nach Versand

```json
POST https://login.hero-software.de/api/v1/Projects/create

Body für Statusupdate (project_match):
{
  "project_match": {
    "status_code": 601,
    "comment": "Angebot {{ANGEBOTSNUMMER}} am {{DATUM}} per E-Mail versendet. Erstellt durch Make.com Automation."
  }
}
```

Status-Codes HERO:
- `201` = Erstkontakt
- `601` = Angebotserstellung  
- `602` = Angebot versendet ← wir setzen diesen
- `801` = Auftrag
- `901` = Abgeschlossen

---

## Teams-Benachrichtigung nach Versand

```
📄 Neues Angebot versendet

Nummer: {{ANGEBOTSNUMMER}}
Kunde: {{KUNDENNAME}} ({{FIRMA}})
Betrag: {{GESAMT_BRUTTO}} € brutto
Gültig bis: {{GUELTIG_BIS}}

[Link zu SharePoint] | [Link in HERO]
```

---

## Sicherheitsregeln für WF3

- Angebot IMMER erst als Outlook-Draft — Meister gibt Freigabe bevor es rausgeht
- Ausnahme nach Freigabe durch Kunden: Standard-Angebote unter €500 können auto-senden
- Kalkulationswerte (Stundensätze) als Make-Variablen speichern → einfach anpassbar
- NIEMALS Preise unter Mindestmarge → Validierung einbauen: wenn gesamt_netto < 0 → Fehler
- Alle generierten Angebote in SharePoint + in HERO dokumentiert
