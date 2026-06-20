# Onboarding Checklist — Was der Kunde vor Projektstart braucht

**Schicke diese Liste nach Auftragsbestätigung, mindestens 2–3 Tage vorher.**

---

## Kritisch (Blocker — ohne diese kann nicht gestartet werden)

- [ ] **Make.com Account** — Team oder Pro Plan (kein Free-Plan, der hat zu wenige Operationen)
  - URL: https://www.make.com/en/pricing
  - Team-Plan reicht für den Start (~€10.59/Monat)

- [ ] **OpenAI API Key** (oder Azure OpenAI — empfohlen für DSGVO)
  - OpenAI: https://platform.openai.com/api-keys → neuen Key erstellen
  - Azure OpenAI: über Azure Portal (dauert 1–2 Tage Aktivierung — früh beantragen!)
  - Budget: ~€20–50/Monat für normales Volumen

- [ ] **Microsoft 365 Admin-Zugang**
  - Zugang zu: Outlook, SharePoint, OneDrive
  - Admin-Rolle nötig für OAuth App-Registrierung in Azure AD
  - Kontakt: IT-Admin der Firma

- [ ] **HERO Software API Key**
  - Jetzt anfragen bei: support@heroapp.de
  - Betreff: "API-Zugang für Make.com Integration"
  - Bearbeitungszeit: 1–3 Werktage

---

## Wichtig (in der ersten Session klären)

- [ ] **Welche 3 Use Cases haben höchste Priorität?**
  (Email-Automatisierung / Dokumentenverarbeitung / Angebot-Generator)

- [ ] **Wer ist die Person, die später selbstständig weiterarbeiten soll?**
  (Name, Rolle, technisches Niveau — damit ich das Coaching anpasse)

- [ ] **Welche E-Mail-Ordner soll der Workflow überwachen?**
  (Inbox? Bestimmte Ordner? Filter nach Betreff?)

- [ ] **Gibt es bereits eine SharePoint-Struktur?** 
  (Oder baut der Kunde sie neu auf? — ich schlage eine Standardstruktur vor)

- [ ] **Welche Dokumenttypen kommen am häufigsten rein?**
  (Rechnungen von Lieferanten, Kundenanfragen als PDF, Lieferscheine...?)

- [ ] **Welche Gewerke/Tätigkeiten hat die Firma?**
  (Elektro, Sanitär, Bau...? — für korrekte Fachsprache in KI-Prompts)

---

## Nice to have (hilfreich aber nicht blockierend)

- [ ] 20–30 Beispiel-E-Mails aus dem Posteingang (anonymisiert) für Testläufe
- [ ] 5–10 Beispiel-PDFs: Rechnungen, Lieferscheine, Angebote
- [ ] Firmen-Briefkopf / Word-Vorlage für Angebote
- [ ] Preisliste / Stundenverrechnungssätze (für Angebot-Generator)
- [ ] HERO Software Zugangsdaten (Lesezugriff) für Mapping

---

## Was der Kunde NICHT braucht

- ❌ Programmierkenntnisse
- ❌ Docker oder Server
- ❌ Separate Datenbank (M365 und HERO übernehmen das)
- ❌ Zusätzliche Software-Lizenzen außer den genannten

---

## Kosten für den Kunden (monatlich, nach dem Projekt)

| Tool | Kosten/Monat |
|------|-------------|
| Make.com Team | ~€10–20 |
| OpenAI API | ~€20–50 (je nach Volumen) |
| Microsoft 365 | bereits vorhanden |
| HERO Software | bereits vorhanden |
| **Gesamt** | **~€30–70/Monat** |

---

## Timeline-Warnung

> ⚠️ Den HERO API Key **sofort** bei HERO Support anfragen.  
> Ohne diesen Key kann Workflow 3 (Angebot-Generator) in der Projektwoche nicht vollständig getestet werden.  
> Fallback: Wir bauen WF3 mit Excel/SharePoint und migrieren zu HERO sobald der Key da ist.
