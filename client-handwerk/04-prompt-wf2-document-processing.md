# WF2 — Dokumentenverarbeitung & Auto-Ablage: OpenAI System Prompts

## Aufbau des Workflows

```
Trigger: Outlook Attachment ODER OneDrive "Eingang"-Ordner
  → Make AI Extractor (Text aus PDF/Word extrahieren)
  → OpenAI: DOKUMENTKLASSIFIKATION (Prompt A) → JSON
  → Router (nach document_type)
     ├── Rechnung (eingehend)   → SharePoint /Eingangsrechnungen/{year}/{month}/
     │                            + Excel-Log + Teams Alert (Betrag > 500€)
     ├── Ausgangsrechnung       → SharePoint /Ausgangsrechnungen/{year}/{month}/
     ├── Angebot (eingehend)    → SharePoint /Angebote/{year}/{Lieferant}/
     ├── Lieferschein           → SharePoint /Projekte/{projekt_id}/Lieferscheine/
     ├── Vertrag                → SharePoint /Vertraege/{year}/ + Teams Alert
     ├── Bauplan/Zeichnung      → SharePoint /Projekte/{projekt_id}/Plaene/
     └── Sonstiges              → SharePoint /Eingang-Manuell-Pruefen/
  → (Optional) HERO: Dokument an Projekt anhängen
```

---

## Prompt A — Dokumentklassifikation & Extraktion

```
Du bist ein intelligenter Dokumentenparser für einen deutschen Handwerksbetrieb.

Analysiere den folgenden Dokumententext und extrahiere alle relevanten Informationen.

Klassifiziere das Dokument in GENAU EINEN der folgenden Typen:
- EINGANGSRECHNUNG: Rechnung die wir erhalten haben (von Lieferant/Subunternehmer)
- AUSGANGSRECHNUNG: Rechnung die wir ausgestellt haben (an unseren Kunden)
- ANGEBOT_EINGEHEND: Angebot das wir von einem Lieferanten erhalten haben
- LIEFERSCHEIN: Lieferschein / Packzettel
- VERTRAG: Vertrag, Rahmenvertrag, Werkvertrag
- AUFTRAGSBESTAETIGUNG: Bestätigung eines Auftrags
- BAUPLAN: Bauplan, Zeichnung, technische Zeichnung, Aufmaß
- SONSTIGES: Alles andere

Extrahiere:
- absender: Firmenname des Absenders (oder null)
- empfaenger: Firmenname des Empfängers (oder null)  
- dokument_nummer: Rechnungs-/Angebots-/Lieferscheinnummer (oder null)
- datum: Dokumentdatum im Format YYYY-MM-DD (oder null)
- betrag_netto: Nettobetrag als Zahl ohne Währung (oder null)
- betrag_brutto: Bruttobetrag als Zahl ohne Währung (oder null)
- mwst_satz: MwSt-Satz als Zahl z.B. 19 (oder null)
- projekt_referenz: Projektnummer, Bauvorhaben, Referenz (oder null)
- faelligkeitsdatum: Zahlungsfrist im Format YYYY-MM-DD (oder null)
- beschreibung: 1 Satz was dieses Dokument enthält
- empfohlener_ordner: einer von: Eingangsrechnungen / Ausgangsrechnungen / Angebote / Lieferscheine / Vertraege / Bauplaene / Eingang-Manuell-Pruefen

Antworte AUSSCHLIESSLICH als gültiges JSON. Kein Text davor oder danach.

Schema:
{
  "document_type": "string",
  "absender": "string|null",
  "empfaenger": "string|null",
  "dokument_nummer": "string|null",
  "datum": "string|null",
  "betrag_netto": number|null,
  "betrag_brutto": number|null,
  "mwst_satz": number|null,
  "projekt_referenz": "string|null",
  "faelligkeitsdatum": "string|null",
  "beschreibung": "string",
  "empfohlener_ordner": "string"
}
```

**Make.com Einstellungen:**
- Model: `gpt-4o` (Vision falls PDF als Bild gescannt)
- Temperature: `0` (deterministisch)
- Response Format: JSON Object
- Max Tokens: `500`

---

## Dateiname-Konvention (automatisch generiert in Make.com)

```
Format: {YYYY-MM-DD}_{document_type}_{absender}_{dokument_nummer}.pdf

Beispiele:
2026-06-21_EINGANGSRECHNUNG_Mueller-GmbH_R-2026-0547.pdf
2026-06-21_LIEFERSCHEIN_Bauhaus-AG_LS-78234.pdf
2026-06-21_VERTRAG_Schmidt-Elektro_V-2026-012.pdf
```

Make.com Formula für Dateiname:
```
{{formatDate(now; "YYYY-MM-DD")}}_{{openai.document_type}}_{{replace(openai.absender; " "; "-")}}_{{openai.dokument_nummer}}.pdf
```

---

## SharePoint Ordnerstruktur

```
/HandwerkDokumente/
├── Eingangsrechnungen/
│   ├── 2026/
│   │   ├── 01_Januar/
│   │   ├── 06_Juni/
│   │   └── ...
├── Ausgangsrechnungen/
│   └── 2026/
├── Angebote/
│   └── 2026/
├── Lieferscheine/
│   └── 2026/
├── Vertraege/
│   └── 2026/
├── Projekte/
│   ├── P-2026-001_Mustermann/
│   │   ├── Lieferscheine/
│   │   ├── Plaene/
│   │   └── Korrespondenz/
│   └── P-2026-002_Schmidt/
└── Eingang-Manuell-Pruefen/    ← KI war unsicher
```

---

## Excel-Log Schema (SharePoint List oder Excel Online)

| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| Datum_Eingang | Date | Automatisch: today() |
| Dokument_Typ | Text | Aus JSON |
| Absender | Text | Aus JSON |
| Dokument_Nummer | Text | Aus JSON |
| Betrag_Netto | Number | Aus JSON |
| Betrag_Brutto | Number | Aus JSON |
| Faelligkeit | Date | Aus JSON |
| Projekt_Referenz | Text | Aus JSON |
| SharePoint_Link | URL | Direkt-Link zum Dokument |
| Status | Choice | Offen / Bezahlt / Geprüft |

---

## Sicherheitsregeln für WF2

- Original-Datei NIEMALS löschen — nur kopieren/verschieben
- Bei Klassifikation-Unsicherheit → in `/Eingang-Manuell-Pruefen/` ablegen + Teams Alert
- Error Handler: Bei OpenAI Fehler → Datei in `/Eingang-Manuell-Pruefen/` + Alert
- Eingangsrechnungen > €1.000 → zusätzlich Teams Alert an Geschäftsführer
- Verträge → IMMER Teams Alert, NIEMALS still ablegen
