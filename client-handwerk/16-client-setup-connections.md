# Einrichtung der Verbindungen in Make.com — Schritt-für-Schritt

**Für:** Einmalige Einrichtung beim Onboarding-Termin (ca. 30–45 Minuten)  
**Wer macht es:** Sie selbst, mit Unterstützung per Bildschirmfreigabe

---

## Was wird eingerichtet?

| Verbindung | Wozu | Wann |
|------------|------|------|
| Microsoft 365 | Outlook, Teams, SharePoint | Heute — Pflicht |
| OpenAI | KI-Texterstellung | Heute — Pflicht |
| HERO Software | Projekt- und Kundendaten | Sobald API-Token von HERO Support kommt |
| Make.com Custom Variables | Sichere Speicherung von API-Tokens | Nach Upgrade auf Pro-Plan |

---

## Schritt 1 — Microsoft 365 verbinden

**Eine Verbindung gilt für alle Microsoft-Apps** (Outlook, Teams, SharePoint, Kontakte).

1. Make.com öffnen → **Scenarios** → WF1 (Email Intelligence Hub) anklicken
2. Auf das erste rote Modul klicken (Outlook-Symbol mit rotem Ausrufezeichen)
3. Im Dialog: **"Add"** klicken
4. Verbindungsname eingeben: `Microsoft 365 - [Firmenname]`
5. **"Sign in with Microsoft"** klicken
6. Microsoft-Login-Fenster öffnet sich → mit Ihrem **Firmen-Microsoft-Account** anmelden
   - ⚠️ **Wichtig:** Firmen-Account (z.B. `max@ihrefirma.de`), NICHT privater Outlook/Hotmail-Account
7. Berechtigungsanfrage bestätigen → **"Akzeptieren"** klicken
8. Verbindung erscheint als aktiv (grünes Häkchen)

✅ **Diese eine Verbindung gilt automatisch für alle anderen Microsoft-Module** in WF1–WF5.  
Bei den weiteren roten Modulen einfach die bereits erstellte Verbindung auswählen — kein erneutes Anmelden.

---

## Schritt 2 — OpenAI verbinden

1. In WF1 auf das **OpenAI-Modul** klicken (roter Kreis mit KI-Symbol)
2. **"Add"** klicken
3. Verbindungsname: `OpenAI - [Firmenname]`
4. **API Key** einfügen (aus dem Onboarding-Dokument — zuvor von Ihnen erstellt auf platform.openai.com)
5. **"Save"** klicken

✅ Diese Verbindung gilt für alle OpenAI-Module in WF1, WF3, WF4.

---

## Schritt 3 — Microsoft 365 Verbindung auf alle Workflows übertragen

Nach Schritt 1 und 2 für WF1:

1. WF2 öffnen → alle roten Module anklicken → jeweils die erstellte Verbindung auswählen
2. WF3 öffnen → gleich
3. WF4 öffnen → gleich
4. WF5 öffnen → gleich

**Keine neue Anmeldung nötig** — die Verbindung aus Schritt 1 einfach auswählen.

---

## Schritt 4 — Teams IDs eintragen

WF1, WF2, WF3, WF4 senden Benachrichtigungen an ein Teams-Kanal. Dafür werden zwei IDs benötigt.

**Team-ID ermitteln:**
1. Microsoft Teams öffnen
2. Ihr Team auswählen → ⋯ (drei Punkte) → **"Link zum Team abrufen"**
3. In der URL finden: `groupId=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`
4. Diesen Wert als `TEAM_ID_HIER_EINTRAGEN` in Make.com eintragen

**Kanal-ID ermitteln:**
1. Im Teams: gewünschten Kanal rechtsklicken → **"Link zum Kanal abrufen"**
2. In der URL finden: `channel/XXXXXXXX...`
3. Diesen Wert als `CHANNEL_ID_HIER_EINTRAGEN` eintragen

---

## Schritt 5 — SharePoint IDs eintragen (für WF2, WF3, WF5)

Das PowerShell-Skript `09-sharepoint-setup.ps1` ermittelt alle IDs automatisch.

**Ausführen (einmalig, Windows PowerShell):**
```powershell
# Skript starten:
.\09-sharepoint-setup.ps1
```

Das Skript gibt aus:
- `SHAREPOINT_SITE_ID` → in Make.com Custom Variables eintragen
- `SHAREPOINT_DRIVE_ID` → in Make.com Custom Variables eintragen
- `SHAREPOINT_LIBRARY_ID` → in Make.com Custom Variables eintragen

Außerdem legt das Skript automatisch die Ordnerstruktur in SharePoint an.

---

## Schritt 6 — HERO API Token eintragen (sobald erhalten)

Voraussetzung: Token wurde von support@heroapp.de zugeschickt.

1. Make.com → **Scenarios → Custom Variables** (linkes Menü, Pro-Plan erforderlich)
2. Variable `HERO_API_TOKEN` auswählen → Token einfügen → **Speichern**

Betroffen: WF3, WF2b (Projektprozess), WF5 (Sync).

---

## Schritt 7 — Confidential Mode prüfen

Für jeden Workflow vor der Aktivierung:

1. Scenario öffnen → **Settings** (Zahnrad-Symbol, oben rechts)
2. **Confidential** = ✓ aktiviert prüfen
3. Falls nicht: aktivieren → Speichern

---

## Schritt 8 — Erster Testlauf

**Reihenfolge:**

1. **WF4** zuerst (kein HERO-Token nötig, einfachster Test):
   - Scenario öffnen → **"Run once"** klicken
   - Testdaten über den Webhook schicken (Beispiel-Payload im Onboarding-Dokument)
   - Outlook Entwürfe prüfen: Mahnung und Auftragsbestätigung müssen erscheinen

2. **WF1** (Outlook Watch):
   - **"Run once"** klicken
   - Eine echte E-Mail an Ihre Outlook-Inbox schicken
   - Scenario soll die E-Mail abfangen → KI klassifiziert → Entwurf wird erstellt

3. **WF2b** (Projektprozess) nach HERO-Token:
   - Ein Testprojekt in HERO anlegen → Scenario soll es erkennen und SharePoint-Ordner erstellen

---

## Checkliste — Einrichtung abgeschlossen?

- [ ] Microsoft 365 Verbindung erstellt und in WF1–WF5 ausgewählt
- [ ] OpenAI Verbindung erstellt und in WF1, WF3, WF4 ausgewählt
- [ ] Teams-IDs eingetragen (Team-ID + Kanal-ID)
- [ ] SharePoint-Ordnerstruktur angelegt (09-sharepoint-setup.ps1 ausgeführt)
- [ ] SharePoint-IDs in Custom Variables eingetragen
- [ ] Confidential Mode in allen Scenarios aktiv
- [ ] WF4 Testlauf erfolgreich (Outlook Entwurf erscheint)
- [ ] WF1 Testlauf erfolgreich (E-Mail erkannt + Entwurf erstellt)
- [ ] HERO API Token in Custom Variables eingetragen (nach Erhalt)
- [ ] WF2b + WF5 Testlauf erfolgreich (nach HERO-Token)

---

## Bei Problemen

| Problem | Lösung |
|---------|--------|
| Rotes Modul nach Verbindungsauswahl | Verbindung hat keine Berechtigung → OAuth neu durchführen mit Admin-Account |
| "Invalid credentials" | OpenAI-Guthaben leer → platform.openai.com → Billing → Guthaben aufladen |
| HERO antwortet nicht | Token abgelaufen → support@heroapp.de kontaktieren |
| Teams-Nachricht kommt nicht an | Team-ID oder Kanal-ID falsch → Schritt 4 wiederholen |
| SharePoint-Ordner wird nicht erstellt | SHAREPOINT_DRIVE_ID falsch → Skript erneut ausführen |

---

## Break-Glass: Notfall-Abschaltung

Falls die Automatisierung falsch läuft — **sofort:**

1. Make.com → alle Scenarios deaktivieren (Schieberegler auf AUS)
2. Microsoft 365 Admin Center → Make.com App-Berechtigung entfernen
3. support@heroapp.de → HERO API Token deaktivieren lassen

Danach ruhig analysieren was passiert ist — keine Daten werden gelöscht.
