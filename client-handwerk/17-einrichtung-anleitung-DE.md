# Einrichtungsanleitung — Make.com Automatisierung für Ihren Handwerksbetrieb

**Für:** Einmalige Einrichtung beim Start  
**Zeitaufwand:** ca. 2–3 Stunden (aufgeteilt auf 2 Tage empfohlen)  
**Vorkenntnisse:** keine erforderlich

---

## Was Sie benötigen — Übersicht

| Tool | Plan | Kosten/Monat | Wozu |
|------|------|-------------|------|
| [Make.com](https://make.com/en/pricing) | Pro | ~$16 | Automatisierung (das „Gehirn") |
| [Microsoft 365 Business Basic](https://www.microsoft.com/de-de/microsoft-365/business/compare-all-plans) | Business Basic | ~$6 | Outlook, Teams, SharePoint |
| [OpenAI API](https://platform.openai.com) | Pay-as-you-go | ~$10–20 | KI-Texterstellung |
| HERO Software | bereits vorhanden | — | Ihre Projekte & Kundendaten |
| **Gesamt** | | **ca. $32–42/Monat** | |

> 💡 **Hinweis:** Microsoft 365 Business Basic unterscheidet sich von einem privaten Outlook/Hotmail-Konto. Nur mit dem Business-Konto funktionieren Teams und SharePoint in der Automatisierung.

---

## Schritt 1 — Make.com Pro buchen

**Was ist Make.com?**  
Make.com ist das Programm, das alle Ihre Workflows steuert. Es verbindet Outlook, Teams, HERO und die KI miteinander.

1. Gehen Sie auf [make.com/en/pricing](https://www.make.com/en/pricing)
2. Wählen Sie **Pro** ($16/Monat)
3. Klicken Sie auf **Get started**
4. Registrieren Sie sich mit Ihrer geschäftlichen E-Mail-Adresse
5. Zahlungsdaten eingeben und bestätigen

✅ **Fertig, wenn:** Sie sich bei [eu1.make.com](https://eu1.make.com) einloggen können

---

## Schritt 2 — Microsoft 365 Business Basic einrichten

**Was ist das?**  
Ihr geschäftliches Microsoft-Konto — gibt Ihnen Outlook, Teams und SharePoint, die die Automatisierung braucht.

1. Gehen Sie auf [microsoft.com/de-de/microsoft-365/business](https://www.microsoft.com/de-de/microsoft-365/business/compare-all-plans)
2. Wählen Sie **Microsoft 365 Business Basic**
3. Klicken Sie auf **Kostenlos testen** (30 Tage gratis) oder direkt kaufen
4. Registrieren Sie Ihre Firmen-Domain (z.B. `info@ihrefirma.de`)
5. Richten Sie Ihr Passwort ein und loggen Sie sich ein unter [outlook.office.com](https://outlook.office.com)

✅ **Fertig, wenn:** Sie sich bei Outlook mit Ihrer Firmen-E-Mail einloggen können

---

## Schritt 3 — OpenAI API-Zugang einrichten

**Was ist das?**  
Die KI, die Ihre E-Mails schreibt und Texte erstellt. Achtung: Das ist **nicht** dasselbe wie ChatGPT — es ist ein separater Zugang.

1. Gehen Sie auf [platform.openai.com](https://platform.openai.com)
2. Klicken Sie auf **Sign up** und registrieren Sie sich
3. Links im Menü: **API Keys** → **+ Create new secret key**
4. Name eingeben: `Make.com Handwerk` → **Create**
5. Den angezeigten Key **sofort kopieren und sicher aufbewahren** — er wird nur einmal angezeigt!
6. Gehen Sie zu **Settings → Billing → Add payment method**
7. Kreditkarte hinterlegen und **$10 Guthaben** aufladen

✅ **Fertig, wenn:** Sie einen API-Key haben (beginnt mit `sk-...`)

---

## Schritt 4 — HERO API-Token anfordern

**Was ist das?**  
Ein Zugangscode, mit dem Make.com Ihre HERO-Projekte lesen kann.

Senden Sie diese E-Mail an **support@heroapp.de**:

---
> **Betreff:** API-Zugang für Make.com Integration
>
> Sehr geehrte Damen und Herren,
>
> ich möchte meinen HERO-Account mit Make.com verbinden, um Projekte automatisch zu verarbeiten. Bitte stellen Sie mir einen API-Token für den externen Zugriff bereit.
>
> Mit freundlichen Grüßen  
> [Ihr Name]

---

⏳ **Bearbeitungszeit:** 1–3 Werktage  
✅ **Fertig, wenn:** Sie eine E-Mail mit Ihrem Token erhalten haben

---

## Schritt 5 — Teams-IDs herausfinden und notieren

**Was ist das?**  
Make.com braucht zwei Codes, um Nachrichten in Ihr Teams zu schicken.

**Team-ID ermitteln:**
1. Öffnen Sie **Microsoft Teams**
2. Klicken Sie links auf Ihr Team
3. Klicken Sie auf **⋯** (drei Punkte) neben dem Team-Namen
4. Wählen Sie **„Link zum Team abrufen"**
5. In der URL suchen Sie: `groupId=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`
6. Diesen Wert kopieren → das ist Ihre **Team-ID**

**Kanal-ID ermitteln:**
1. Klicken Sie im Team auf den gewünschten Kanal (z.B. „Allgemein")
2. Rechtsklick → **„Link zum Kanal abrufen"**
3. In der URL den Teil nach `channel/` kopieren → das ist Ihre **Kanal-ID**

📝 **Notieren Sie beide Werte** in einer Textdatei auf Ihrem Desktop

---

## Schritt 6 — SharePoint-IDs herausfinden (für WF2, WF3, WF5)

**Was ist das?**  
SharePoint ist Ihre digitale Ablage — Make.com legt dort automatisch Projektordner an.

Führen Sie das mitgelieferte Skript aus:

1. Öffnen Sie **Windows PowerShell** (Startmenü → „PowerShell" suchen)
2. Navigieren Sie zum Projektordner und führen Sie aus:
```powershell
.\09-sharepoint-setup.ps1
```
3. Beim ersten Start: Microsoft-Login mit Ihrem Business-Account bestätigen
4. Das Skript gibt aus:
   - `SHAREPOINT_SITE_ID`
   - `SHAREPOINT_DRIVE_ID`
   - `SHAREPOINT_LIBRARY_ID`

📝 **Alle drei Werte notieren**

---

## Schritt 7 — Verbindungen in Make.com einrichten

Jetzt verknüpfen Sie Make.com mit Ihren anderen Programmen.

1. Öffnen Sie [eu1.make.com](https://eu1.make.com) → **Scenarios**
2. Importieren Sie den ersten Workflow (Anleitung bekommen Sie vom Techniker)
3. Klicken Sie auf jedes **rot markierte Modul**
4. Wählen Sie die passende Verbindung:

| Modul-Farbe | Programm | Was tun |
|-------------|----------|---------|
| 🔵 Blau (Outlook) | Microsoft 365 Email | „Add" → mit Business-Account einloggen |
| 🟣 Lila (Teams) | Microsoft Teams | dasselbe Microsoft-Konto auswählen |
| 🟢 Grün (OpenAI) | OpenAI | „Add" → API Key einfügen |

✅ **Fertig, wenn:** Alle Module keine roten Markierungen mehr haben

---

## Schritt 8 — Custom Variables in Make.com anlegen

**Was ist das?**  
Sicherer Speicherort für Ihre API-Tokens in Make.com (nur mit Pro-Plan verfügbar).

1. Make.com → links im Menü → **More → Custom Variables** (oder unter Settings)
2. Klicken Sie auf **+ Add variable**
3. Folgende Variablen anlegen:

| Variable | Wert |
|----------|------|
| `HERO_API_TOKEN` | Token von support@heroapp.de |
| `SHAREPOINT_SITE_ID` | Aus Schritt 6 |
| `SHAREPOINT_DRIVE_ID` | Aus Schritt 6 |
| `SHAREPOINT_LIBRARY_ID` | Aus Schritt 6 |
| `TEAM_ID` | Aus Schritt 5 |
| `CHANNEL_ID` | Aus Schritt 5 |

---

## Schritt 9 — Erster Testlauf

**Beginnen Sie mit WF4** — dem einfachsten Workflow (kein HERO, kein SharePoint nötig).

1. Make.com → WF4 öffnen
2. Klicken Sie auf **„Run once"**
3. Schicken Sie eine Test-Anfrage an die Webhook-URL (erhalten Sie vom Techniker)
4. Prüfen Sie Ihr **Outlook** → Ordner **Entwürfe**
5. Ein fertiger E-Mail-Entwurf sollte erscheinen ✅

---

## Checkliste — Alles bereit?

- [ ] Make.com Pro-Account erstellt
- [ ] Microsoft 365 Business Basic aktiviert
- [ ] OpenAI API-Key erstellt und $10 Guthaben aufgeladen
- [ ] E-Mail an support@heroapp.de gesendet
- [ ] Team-ID und Kanal-ID notiert
- [ ] SharePoint-Skript ausgeführt, alle 3 IDs notiert
- [ ] Alle Verbindungen in Make.com eingerichtet (keine roten Module)
- [ ] Custom Variables befüllt
- [ ] WF4 Testlauf erfolgreich (Entwurf erscheint in Outlook)

---

## Notfall — Was tun wenn etwas schiefläuft?

| Problem | Lösung |
|---------|--------|
| Make.com zeigt rote Module | Verbindung klicken → neu einloggen |
| „Invalid credentials" bei OpenAI | Guthaben leer → platform.openai.com → Billing → aufladen |
| Teams-Nachricht kommt nicht an | Team-ID oder Kanal-ID prüfen (Schritt 5 wiederholen) |
| HERO antwortet nicht | Token abgelaufen → support@heroapp.de kontaktieren |
| Workflow läuft nicht an | Make.com → Scenario → Toggle auf „AN" stellen |

**Sofort-Stopp falls etwas falsch läuft:**
1. Make.com → alle Scenarios deaktivieren (Schalter auf AUS)
2. Microsoft 365 Admin Center → Make.com-App-Berechtigung entfernen
3. support@heroapp.de → HERO API-Token deaktivieren lassen

---

*Bei Fragen wenden Sie sich an Ihren Techniker.*
