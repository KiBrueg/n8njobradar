# Security & DSGVO Checkliste — Handwerk Automatisierung

Vor Produktivbetrieb jeden Punkt abhaken. Für Kunden ausdrucken + unterschreiben lassen.

---

## 1. Datenschutz (DSGVO / Art. 5, 25, 28)

### Auftragsverarbeitung

- [ ] **Make.com DPA (Auftragsverarbeitungsvertrag)** abschließen
  - make.com/en/legal/data-processing-addendum
  - Pflicht wenn Kundendaten durch Make.com verarbeitet werden (sie werden es)

- [ ] **OpenAI DPA** abschließen (falls OpenAI API, nicht Azure)
  - platform.openai.com/privacy → Enterprise DPA
  - Standard API: Daten werden NICHT für Training verwendet (API ToS §3)
  - Für maximale Sicherheit: Azure OpenAI mit EU-Region (West Europe / Germany)

- [ ] **Microsoft 365 DSGVO** — bereits durch Microsoft MCA (Microsoft Customer Agreement) abgedeckt wenn Business-Plan

- [ ] **HERO Software** — deutsches Unternehmen, DSGVO-konform per Herstellerangabe. DPA bei hero-software.de anfragen.

### Datensparsamkeit

- [ ] Scenario in Make.com als **Confidential** markieren:
  Scenario → Settings → Enable Confidential Mode → Save
  (Logs zeigen keine Kundendaten mehr)

- [ ] **Keine Kundendaten in Teams-Nachrichten** die nicht notwendig sind
  → Nur: Name, Kategorie, Betrag. KEINE vollständigen E-Mail-Texte in Teams posten.

- [ ] **Automatische Log-Löschung** in Make.com konfigurieren:
  Organization → Settings → Data Retention → max. 30 Tage

---

## 2. Zugriffsschutz

### Make.com

- [ ] **2FA aktivieren** für alle Make.com Accounts
- [ ] **API-Token** niemals in Scenario-Mappern hardcoden → immer Custom Variables
- [ ] Webhook-URLs als **geheim behandeln** (= API Key) — nie öffentlich teilen
- [ ] Nur benötigte **OAuth2-Scopes** für Microsoft Connection:
  - Mail.ReadWrite (nicht Mail.Read wenn wir auch verschieben/Draft erstellen)
  - Calendars.ReadWrite (nur wenn Kalender-Feature aktiv)
  - Files.ReadWrite.All (für SharePoint)
  - Team.ReadBasic.All + ChannelMessage.Send (für Teams)

### HERO Software

- [ ] **HERO API-Token** ausschließlich in Make.com Custom Variables speichern
- [ ] Token-Rotation: Neuen Token anfordern wenn Mitarbeiter das Unternehmen verlässt
- [ ] Minimale Berechtigungen: API-Token sollte nur Lese-/Schreibzugriff auf Projekte/Kontakte haben — keine Admin-Rechte

### Microsoft 365

- [ ] **SharePoint Versionierung aktivieren** (schützt vor ungewolltem Überschreiben):
  SharePoint → Library Settings → Versioning Settings → Major versions → Keep 50 versions
- [ ] **SharePoint-Bibliothek Berechtigungen** prüfen:
  Nur der Automatisierungs-Account + Büro-Mitarbeiter haben Zugriff
  (kein öffentlicher Zugriff)
- [ ] **Microsoft 365 MFA** für alle Accounts inklusive dem Automatisierungs-Account

---

## 3. KI-Sicherheit (Halluzinations- und Fehler-Schutz)

### Nie automatisch senden

- [ ] **WF1:** Alle E-Mails → Outlook Draft. Niemals `microsoft-365-email:sendAMessage` in WF1 verwenden.
- [ ] **WF3:** Angebote → Outlook Draft. Niemals auto-senden ohne menschliche Freigabe.
- [ ] **Ausnahme erst nach Bewährungsphase** (nach 30 Tagen erfolgreichen Betrieb, maximal für TERMIN-Bestätigungen)

### Validierung

- [ ] WF3: Mindestauftragswert-Check (< 200 € → kein Auto-Angebot)
- [ ] WF2: `sicher_klassifiziert = false` → manueller Prüfungsordner + Teams Alert
- [ ] WF1: Wenn OpenAI kein JSON zurückgibt → Error Handler → Teams Alert, E-Mail unverändert lassen

### Prompt Injection Schutz

- [ ] E-Mail-Texte werden als User-Message übergeben, System-Prompt ist fest
- [ ] Maximale Token-Länge begrenzt (`max_tokens`), damit keine exzessiven Outputs entstehen
- [ ] **Vorsicht bei:** E-Mails die Anweisungen an die KI enthalten könnten ("Ignoriere alle vorherigen Anweisungen...")
  → Mitigation: Temperature 0 + Response Format JSON Object macht Injection deutlich schwieriger

---

## 4. Datenverlust-Schutz (Datenbank-Schutz)

### SharePoint (primärer Dokumentenspeicher)

- [ ] **Versioning aktiviert** (siehe oben)
- [ ] **Papierkorb-Aufbewahrung:** SharePoint → Site Settings → Recycle Bin → Items are kept for 93 days
- [ ] **Kein Delete-Modul** in irgendwelchen Make.com Scenarios
- [ ] Einmal pro Quartal: manuelles Backup der SharePoint-Bibliothek als Download

### HERO Datenbank

- [ ] HERO macht **interne automatische Backups** (Herstellerangabe) — für Kundendaten kein zusätzliches Backup nötig
- [ ] **HERO hat kein Löschen über API** — Create/Update only — Datenbank-Schutz ist eingebaut
- [ ] Bei Status-Updates: `comment`-Feld dokumentiert immer was und wann geändert wurde

### Make.com

- [ ] **Scenarios vor Änderungen duplizieren** (Scenario → ⋯ → Clone)
- [ ] Keine irreversiblen Aktionen ohne Error-Handler (Delete, Move, etc.)

---

## 5. Betrieb & Monitoring

### Fehler-Alerting

- [ ] **Teams-Kanal "Automation-Fehler"** anlegen
- [ ] Make.com Scenario Settings → **Notifications** → Error Email an Büroleitung
- [ ] In jedem Scenario: **maxErrors: 3** konfiguriert (danach stoppt Scenario statt endlos zu versuchen)

### Kostenkontrolle

- [ ] **OpenAI Usage Limits** setzen: platform.openai.com → Settings → Limits → Hard limit €50/Monat
- [ ] **Make.com Operations-Verbrauch** täglich im Dashboard prüfen (erste 2 Wochen)
- [ ] Bei unerwartetem Spike: Scenario sofort deaktivieren + untersuchen

### Regelmäßige Überprüfung (monatlich)

- [ ] Scenario Execution History durchsehen: Fehler > 5% → Untersuchen
- [ ] OpenAI API-Kosten vs. Einstellungen überprüfen
- [ ] SharePoint-Ordner auf falsch abgelegte Dokumente prüfen
- [ ] HERO: Leads überprüfen die von Automation angelegt wurden — korrekt?

---

## 6. Notfall-Plan (Break-Glass)

Wenn die Automation falsch funktioniert oder bösartig genutzt wird:

```
SOFORT:
1. Make.com → alle Scenarios DEAKTIVIEREN (Schieberegler → Off)
2. Microsoft 365 Admin → App-Registrierung für Make.com entfernen
   (Entzieht Make.com alle Zugriffsrechte sofort)
3. HERO Support kontaktieren: support@heroapp.de → API-Token deaktivieren

DANN UNTERSUCHEN:
4. Make.com Scenario History → letzte Ausführungen ansehen
5. SharePoint Versions-History → welche Dateien wurden verändert?
6. HERO → Aktivitätslog → welche Leads/Projekte wurden angelegt?

WIEDERHERSTELLEN:
7. Fehlkonfiguration korrigieren
8. Neue API-Tokens/Credentials ausstellen
9. Test-Lauf mit bekannten Eingaben
10. Schrittweise wieder aktivieren
```

---

## Unterschrift (Kundenabnahme)

```
Ich bestätige, dass ich diese Checkliste verstanden habe und die beschriebenen
Sicherheitsmaßnahmen umgesetzt sind oder bewusst zurückgestellt wurden:

Datum: ___________________

Unterschrift: ___________________

Position: ___________________
```
