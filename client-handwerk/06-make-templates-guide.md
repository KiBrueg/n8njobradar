# Make.com Templates & Blueprint Import Guide

## Статус: готово к импорту

Все шесть blueprints лежат в этой папке:

| Файл | Workflow | Описание |
|------|----------|----------|
| `10-wf1-email-intelligence.blueprint.json` | WF1 | Email Intelligence Hub (Outlook Watch → AI → Draft + Teams) |
| `11-wf2-document-processing.blueprint.json` | WF2 | Dokument-Ablage & Klassifikation (HERO Poll → SharePoint) |
| `12-wf3-angebot-generator.blueprint.json` | WF3 | Angebot-Generator (Webhook → AI → Outlook Draft) |
| `13-wf4-schriftverkehr.blueprint.json` | WF4 | AI-Schriftverkehr: Mahnung & Auftragsbestätigung → Outlook Draft |
| `14-wf5-hero-m365-sync.blueprint.json` | WF5 | HERO ↔ Microsoft 365 Bidirectional Sync (Contacts + Logbook) |
| `15-wf2-projektprozess.blueprint.json` | WF2b | Projektprozess: HERO AUFTRAG/RECHNUNG → SharePoint-Ordner + Teams |

---

## Как импортировать blueprint в Make.com

1. Make.com → **Scenarios** → кнопка ⋯ (три точки) → **Import Blueprint**
2. Выбрать JSON-файл
3. После импорта: **немедленно подключить все Connections** (показывает оранжевый значок)
4. Вписать все `HIER_EINTRAGEN` значения
5. **Сначала запустить один раз вручную** (Run once) — не активировать автозапуск до теста

---

## Make.com Connections — что нужно подключить

| App | Где в blueprints | Как подключить |
|-----|-----------------|----------------|
| Microsoft 365 Email (Outlook) | WF1, WF2, WF3, WF4, WF5 | Connections → + Add → Microsoft 365 Email → OAuth2 |
| Microsoft Teams | WF1, WF2, WF3, WF4 | Connections → + Add → Microsoft Teams → OAuth2 |
| Microsoft SharePoint | WF2, WF3, WF5 | Connections → + Add → SharePoint → OAuth2 |
| Microsoft 365 People (Contacts) | WF5 | Connections → + Add → Microsoft 365 → OAuth2 (gleiche Verbindung) |
| Microsoft Excel Online | WF2 | Connections → + Add → Microsoft Excel → OAuth2 |
| OpenAI | WF1, WF2, WF3, WF4 | Connections → + Add → OpenAI → API Key |
| Data Store (Make built-in) | WF3, WF5 | Scenarios → Data Stores → Neuen anlegen |

**Achtung:** Ein Microsoft-365-Konto für alle Microsoft-Apps (Email, Teams, SharePoint, People, Excel) reicht — alle nutzen OAuth2 mit demselben Tenant.

---

## Make.com Custom Variables — PFLICHT vor Aktivierung

Unter **Scenarios → Custom Variables** folgende Werte anlegen (erfordert **Pro-Plan**):

| Variable | Wert | Wo verwendet |
|----------|------|-------------|
| `HERO_API_TOKEN` | Bearer-Token von HERO Support | WF1, WF3, WF5 |
| `SHAREPOINT_SITE_ID` | Aus SharePoint URL (Script `09-sharepoint-setup.ps1` liefert das) | WF2, WF3, WF5 |
| `SHAREPOINT_LIBRARY_ID` | Aus SharePoint URL | WF2, WF3 |
| `SHAREPOINT_DRIVE_ID` | Für Excel Online und SharePoint-Ordner | WF2, WF5 |
| `TEAM_ID_HIER_EINTRAGEN` | Teams Team-ID | WF1, WF2, WF3, WF4 |
| `CHANNEL_ID_HIER_EINTRAGEN` | Teams Channel-ID | WF1, WF2, WF3, WF4 |

**Teams IDs ermitteln:** Teams → Team auswählen → ⋯ → Link zum Team abrufen → ID aus URL kopieren. Oder: Teams Admin Center → Teams → [Team] → ID.

---

## WF4-spezifisch: HIER_EINTRAGEN vor Aktivierung

WF4 Schriftverkehr hat einen Webhook-Trigger. Nach Import:
- Webhook-URL aus Make.com kopieren (Scenarios → WF4 → Webhook → URL)
- Diese URL im aufrufenden System (HERO, Formular, etc.) eintragen

WF5 Sync hat zusätzlich:
- Filter `@IHRE-FIRMA.de` in Modul 14 anpassen → durch die echte Firmen-Domain ersetzen (verhindert dass interne E-Mails als Kundenkontakte angelegt werden)

---

## Was bedeuten `__IMTCONN__: 0`?

Das ist ein Platzhalter — Make.com fragt nach dem Import automatisch, welche Connection verwendet werden soll. Einfach die neu erstellten Connections auswählen.

---

## ⚠️ Data Stores: Free-Plan Einschränkung (Workaround aktiv)

**Aktuell (Entwicklungsphase, Free Plan):** Nur 1 Data Store erlaubt.
Workaround: Ein einziger Store `CONFIG - Variablen & API Keys` mit Schlüssel-Präfixen:
- `CONFIG_*` — API Keys und IDs (HERO, SharePoint, Teams)
- `PROD_WF2_*` / `PROD_WF5_*` — Produktions-Zustand
- `TEST_WF2_*` / `TEST_WF5_*` — Test-Zustand

WF5 speichert Sync-State als Schlüssel `last_sync_timestamp` und Kontakt-Mappings als `{email} → {hero_id, m365_contact_id}` im gleichen Store.

**TODO FÜR CLIENT (nach Upgrade auf Pro/Teams):**
Separate Data Stores anlegen — ein Store pro Workflow, klar getrennt:
- `CONFIG - Variablen & API Keys`
- `PROD - WF2 Projektprozess`
- `PROD - WF5 HERO Sync`
- `TEST - WF2 Projektprozess`
- `TEST - WF5 HERO Sync`

Dann in den Blueprints den `datastore`-Parameter auf den jeweiligen Store umstellen.

---

## Welche Make.com Tarif-Features werden benötigt?

| Feature | WF1 | WF2 | WF3 | WF4 | WF5 | Tarif |
|---------|-----|-----|-----|-----|-----|-------|
| Custom Webhooks | — | — | ✓ | ✓ | — | Core+ |
| Data Stores | — | — | ✓ | — | ✓ | Core+ |
| Microsoft 365 Apps | ✓ | ✓ | ✓ | ✓ | ✓ | alle |
| OpenAI | ✓ | ✓ | ✓ | ✓ | — | alle |
| SharePoint | — | ✓ | ✓ | — | ✓ | Core+ |
| Custom Variables (HERO Token) | ✓ | — | ✓ | — | ✓ | **Pro+** |
| Scheduled trigger (alle 15 Min) | — | ✓ | — | — | ✓ | Core+ |

**Minimum für Produktion: Make.com Pro ($16/mo)** — für Custom Variables (HERO_API_TOKEN).
**Empfohlen: Teams ($29/mo)** — für Rollentrennung (Builder + Client-Owner).

---

## Relevante Make.com Template-Vorlagen (Inspiration, kein Import)

Diese offiziellen Templates zeigen den Bauplan ähnlicher Flows — für Orientierung beim Anpassen:

| Template | Was zeigt es | Wo finden |
|----------|-------------|-----------|
| "Monitor Microsoft Email Messages → Upload to OneDrive" | M365 Email trigger + OneDrive upload | make.com/en/templates → suche "Microsoft Email OneDrive" |
| "OpenAI GPT → Microsoft Teams" | OpenAI + Teams Nachricht | make.com/en/templates → suche "OpenAI Teams" |
| "Create Microsoft Outlook Draft" | Outlook Draft workflow | make.com/en/templates → suche "Outlook Draft" |

**Nicht als Blueprint importieren** — eigene Blueprints in dieser Mappe sind vollständiger und auf Handwerksbetrieb zugeschnitten.

---

## Modul-Namen (confirmed vs. inferred)

| Modul | Status | Verwendet in |
|-------|--------|-------------|
| `openai-gpt-3:CreateCompletion` | ✅ Bestätigt (aus GitHub) | WF1, WF2, WF3, WF4 |
| `microsoft-teams:sendMessage` | ✅ Bestätigt (aus GitHub) | WF1, WF2, WF3, WF4 |
| `http:ActionSendData` | ✅ Bestätigt (aus GitHub) | WF1, WF3, WF5 |
| `gateway:CustomWebhook` | ✅ Bestätigt (aus GitHub) | WF3, WF4 |
| `builtin:BasicRouter` | ✅ Bestätigt (Dokumentation) | WF1, WF2, WF3, WF4, WF5 |
| `builtin:BasicFeeder` | ✅ Bestätigt (Dokumentation) | WF2, WF5 |
| `builtin:BasicScheduler` | ✅ Bestätigt (Dokumentation) | WF5 |
| `data-store:GetARecord` | ⚠️ Wahrscheinlich korrekt | WF3, WF5 |
| `data-store:UpdateARecord` | ⚠️ Wahrscheinlich korrekt | WF5 |
| `json:ParseJSON` | ⚠️ Wahrscheinlich korrekt | WF1, WF2, WF3, WF4 |
| `microsoft-365-email:watchEmails` | ⚠️ Wahrscheinlich korrekt | WF1, WF2, WF5 |
| `microsoft-365-email:createADraftMessage` | ⚠️ Wahrscheinlich korrekt | WF1, WF3, WF4 |
| `microsoft-365-email:moveMessage` | ⚠️ Wahrscheinlich korrekt | WF1 |
| `microsoft-365-people:CreateContact` | ⚠️ Wahrscheinlich korrekt | WF5 |
| `microsoft-365-people:UpdateContact` | ⚠️ Wahrscheinlich korrekt | WF5 |
| `sharepoint:uploadAFile` | ⚠️ Wahrscheinlich korrekt | WF2, WF3 |
| `sharepoint:createFolder` | ⚠️ Wahrscheinlich korrekt | WF5 |
| `microsoft-excel:addRow` | ⚠️ Wahrscheinlich korrekt | WF2 |

**Falls ein Modul beim Import nicht erkannt wird:** In Make.com öffnen → Modul anklicken → App-Suche → manuell das richtige Modul auswählen — alle Mapper-Werte bleiben erhalten.

---

## Reihenfolge der Einrichtung

```
Woche 1, Tag 1:
  1. Make.com Pro-Plan aktivieren (für Custom Variables)
  2. Microsoft 365 Connection verbinden (OAuth2 — eine Connection für alle M365-Apps)
  3. OpenAI API Key holen (platform.openai.com → API Keys → "Make.com Handwerk")
  4. HERO API Key bei support@heroapp.de anfragen (braucht 1-3 Tage!)
  5. WF1 importieren → Connections verbinden → Run once testen

Woche 1, Tag 2-3:
  6. SharePoint Ordnerstruktur anlegen (09-sharepoint-setup.ps1)
  7. WF2 + WF2b importieren → testen
  8. WF4 importieren → Webhook-URL holen → testen (kein HERO-Token nötig)

Woche 1, Tag 4-5:
  9.  HERO API Token erhalten → Custom Variables befüllen
  10. WF3 Webhook konfigurieren → importieren → testen
  11. WF5 importieren → @IHRE-FIRMA.de ersetzen → testen
  12. Gesamttest aller 5 Flows
  13. Knowledge Transfer Session mit Client
```
