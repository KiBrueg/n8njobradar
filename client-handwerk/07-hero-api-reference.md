# HERO Software — API Reference (verifiziert)

Quelle: Offizielle HERO API-Dokumentation + Community. Stand: Juni 2026.

---

## API-Key beschaffen

**HERO hat keinen Self-Service für API-Keys.** Token muss manuell angefragt werden:

```
E-Mail an: support@heroapp.de
Betreff: API-Zugang für Automatisierung (Make.com Integration)

Bitte senden Sie mir einen API-Token für externe Integrationen.
Account: [Firmenname / E-Mail-Adresse im HERO-Account]
Verwendungszweck: Make.com Workflow-Automatisierung für Lead-Anlage und Statusupdates
```

**Bearbeitungszeit:** 1–3 Werktage.

---

## REST API — Leads/Projekte anlegen

### Endpoint
```
POST https://login.hero-software.de/api/v1/Projects/create
```

### Headers
```http
Authorization: Bearer [HERO_API_TOKEN]
Content-Type: application/json
```

### Request Body (Mindestfelder)
```json
{
  "measure": "PRJ",
  "customer": {
    "email": "kunde@beispiel.de"
  },
  "address": {
    "zipcode": "10115"
  }
}
```

### Vollständiger Request Body
```json
{
  "measure": "PRJ",
  "customer": {
    "email": "mustermann@beispiel.de",
    "first_name": "Max",
    "last_name": "Mustermann",
    "phone_home": "030 12345678",
    "phone_mobile": "0151 12345678"
  },
  "address": {
    "street": "Musterstraße 1",
    "zipcode": "10115",
    "city": "Berlin"
  },
  "project": {
    "source": "Make.com E-Mail Automation",
    "description": "Automatisch erfasst via E-Mail-Klassifikation"
  },
  "project_match": {
    "status_code": 201,
    "comment": "Lead via automatische E-Mail-Verarbeitung erstellt"
  }
}
```

### Response (Success)
```json
{
  "status": "success",
  "id": 12345
}
```

### Response (Error)
```json
{
  "status": "error",
  "message": "customer.email is required"
}
```

---

## REST API — Status-Update

### Endpoint
```
POST https://login.hero-software.de/api/v1/Projects/create
```

Gleicher Endpoint für Update, aber mit `project_match.id`:

```json
{
  "project_match": {
    "id": "HERO_PROJECT_MATCH_ID",
    "status_code": 602,
    "comment": "Angebot A-2026-0001 am 21.06.2026 per E-Mail versendet"
  }
}
```

---

## Projektstatus-Codes (HERO)

| Code | Bedeutung | Wann setzen |
|------|-----------|------------|
| `201` | Erstkontakt | Bei Lead-Erstellung via E-Mail |
| `601` | Angebotserstellung | Wenn Angebot im Entwurf |
| `602` | Angebot versendet | Nach E-Mail-Versand |
| `801` | Auftrag | Nach Auftragsbestätigung |
| `802` | Auftrag bestätigt | — |
| `901` | Abgeschlossen | Projekt fertig |
| `902` | Verloren | Kein Auftrag erhalten |

---

## GraphQL API — Kundendaten lesen

### Endpoint
```
POST https://login.hero-software.de/api/external/v7/graphql
```

### Headers
```http
Authorization: Bearer [HERO_API_TOKEN]
Content-Type: application/json
```

### Query: Kontakt laden
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

### Make.com HTTP Body dafür:
```json
{
  "query": "query GetContact($id: ID!) { contacts(filter: { id: { eq: $id } }) { id first_name last_name company_name email phone_home phone_mobile addresses { street zipcode city } } }",
  "variables": {
    "id": "{{1.hero_contact_id}}"
  }
}
```

### Response:
```json
{
  "data": {
    "contacts": [
      {
        "id": "123",
        "first_name": "Max",
        "last_name": "Mustermann",
        "company_name": "Mustermann GmbH",
        "email": "max@mustermann.de",
        "phone_home": null,
        "phone_mobile": "0151 12345678",
        "addresses": [
          { "street": "Musterstr. 1", "zipcode": "10115", "city": "Berlin" }
        ]
      }
    ]
  }
}
```

### Query: Projekte laden
```graphql
query GetProjects {
  project_matches(
    filter: { status_code: { in: [201, 601] } }
    limit: 50
  ) {
    id
    status_code
    comment
    created_at
    updated_at
    contact {
      id
      first_name
      last_name
      email
    }
  }
}
```

### Mutation: Kontakt anlegen
```graphql
mutation CreateContact($input: ContactInput!) {
  create_contact(input: $input) {
    id
    first_name
    last_name
    email
  }
}
```

Variables:
```json
{
  "input": {
    "first_name": "Max",
    "last_name": "Mustermann",
    "email": "max@mustermann.de",
    "phone_mobile": "0151 12345678"
  }
}
```

---

## GraphQL — Contacts mit Polling (updated_since)

```graphql
query {
  contacts(updated_since: "2026-06-21T00:00:00Z") {
    id
    nr
    first_name
    last_name
    company_name
    email
    phone_home
    phone_mobile
    address { street zipcode city country }
  }
}
```

`updated_since` — Schlüssel für Polling ohne Duplikate. Im Data Store letzten Timestamp speichern.

---

## GraphQL — Dokumente nach Typ und Status

```graphql
query {
  customer_documents(
    filter: {
      document_type: { base_type: "OFFER" }
      status_code: { eq: "ACCEPTED" }
    }
  ) {
    id
    document_number
    value
    vat
    status_code
    document_type { base_type name }
    contact { id first_name last_name company_name email }
    project_match { id status_code }
  }
}
```

`base_type` Werte: `"OFFER"` (Angebot), `"ORDER"` (Auftrag), `"INVOICE"` (Rechnung).

---

## GraphQL — Logbuch-Eintrag erstellen

```graphql
mutation {
  add_logbook_entry(input: {
    project_match_id: "HERO_PROJECT_ID",
    title: "E-Mail von kunde@beispiel.de",
    text: "Betreff: Anfrage Badezimmer\n\nEingegangen via Make.com Automation."
  }) {
    id
  }
}
```

Verwenden für: jede eingehende E-Mail → als Logbucheintrag in HERO speichern.

---

## Make.com: Native HERO Integration

Make.com hat ein offizielles HERO Software Modul unter:
`apps.make.com/hero-software`

Verfügbare Aktionen (über native Integration):
- Watch Projects (Trigger)
- Watch Contacts (Trigger)
- Create a Project
- Update a Project
- Get a Project
- Create a Contact
- Get a Contact
- Create Logbook Entry
- Watch Tasks

**Für WF3:** Falls der native HERO Connector für Make.com verfügbar ist, einfach den `http:ActionSendData`-Block durch das native Modul ersetzen — sauberer und wartungsfreundlicher.

---

## Fehlerbehandlung in Make.com

```
HERO API antwortet mit:
- 200: success=true → alles OK
- 200: status=error → Validierungsfehler (z.B. fehlende Pflichtfelder)
- 401: Ungültiger Token → Token rotieren
- 429: Rate Limit → maxErrors: 3 in Scenario-Einstellungen schützt davor
- 500: HERO-seitiger Fehler → Error Handler → Teams Alert
```

**In Make.com Error Handler einbauen:**
- `handleErrors: true` im HTTP-Modul aktiviert
- Bei Fehler: `builtin:BasicRouter` mit Bedingung `parseResponse.status = "error"` → Teams Alert

---

## Datenschutz (DSGVO)

- HERO ist ein deutsches Unternehmen, Server in Deutschland/EU
- Kundendaten (Name, E-Mail, Adresse) liegen ausschließlich in HERO + Microsoft 365
- Make.com: Szenario als **Confidential** markieren (Scenario → Settings → Confidential = true) → Logs zeigen keine Payload-Daten
- OpenAI API: Standardmäßig werden Prompts nicht für Training verwendet (API-Nutzung) — für maximale DSGVO-Konformität: Azure OpenAI mit EU-Region verwenden
