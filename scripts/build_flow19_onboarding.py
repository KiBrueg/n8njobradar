"""
Create Flow 19: Course Onboarding Form Webhook.
Receives POST from Tally (or any form) → inserts into course_onboarding_submissions
→ confirmation email to school → Telegram notification to operator.

Tally webhook format: { eventType, createdAt, data: { fields: [{key,label,value},...] } }
Also accepts flat JSON: { school_name, contact_email, course_name, ...rest }
"""
import json, os, ssl, sys, urllib.request

N8N_API_KEY = os.environ["N8N_API_KEY"]
N8N_BASE    = os.environ.get("N8N_BASE", "https://n8n.157.180.112.46.sslip.io")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        N8N_BASE + path, data=data, method=method,
        headers={"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, context=CTX) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {path}: {e.read().decode()[:600]}")

existing = [w for w in req("GET", "/api/v1/workflows?limit=100")["data"]
            if w["name"].startswith("JobRadar -- Flow 19")]
if existing:
    raise SystemExit(f"Flow 19 already exists: {existing[0]['id']}")

PG_CRED    = {"postgres": {"id": os.environ.get("N8N_CRED_POSTGRES", "Tvuhat51UDCzKwnE"),
                            "name": "Postgres account"}}
GMAIL_CRED = {"gmailOAuth2": {"id": os.environ.get("N8N_CRED_GMAIL", "7rf7G4mjBXt01V7T"),
                               "name": "Gmail"}}
TELEGRAM   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = "-1004436898733"

# ── Parse Tally or flat JSON ───────────────────────────────────────────────────
PARSE_JS = r"""
const body = $json.body || $json;

let school_name   = '';
let contact_email = '';
let course_name   = '';
let extras        = {};

// Tally format: { data: { fields: [{key, label, value}] } }
if (body.data && body.data.fields) {
  for (const f of body.data.fields) {
    const lbl = (f.label || f.key || '').toLowerCase();
    const val = Array.isArray(f.value) ? f.value.join(', ') : String(f.value || '');
    if (lbl.includes('schule') || lbl.includes('school') || lbl.includes('einrichtung') || lbl.includes('organisation'))
      school_name = val;
    else if (lbl.includes('email') || lbl.includes('e-mail'))
      contact_email = val;
    else if (lbl.includes('kurs') || lbl.includes('course') || lbl.includes('ausbildung') || lbl.includes('umschulung'))
      course_name = val;
    else
      extras[f.label || f.key] = val;
  }
} else {
  // Flat JSON
  school_name   = body.school_name   || body.schule        || '';
  contact_email = body.contact_email || body.email         || '';
  course_name   = body.course_name   || body.kurs          || body.course || '';
  const {school_name: _, contact_email: __, course_name: ___, email: ____, ...rest} = body;
  extras = rest;
}

if (!school_name)   school_name   = 'Unbekannte Einrichtung';
if (!course_name)   course_name   = 'Unbekannter Kurs';

return { json: { school_name, contact_email, course_name,
                 payload: extras, submitted_at: new Date().toISOString() } };
"""

INSERT_SQL = """
INSERT INTO course_onboarding_submissions
  (school_name, contact_email, course_name, payload, status)
VALUES (
  '{{ $json.school_name.replace(/'/g, "''") }}',
  '{{ $json.contact_email.replace(/'/g, "''") }}',
  '{{ $json.course_name.replace(/'/g, "''") }}',
  '{{ JSON.stringify($json.payload) }}'::jsonb,
  'new'
)
RETURNING id, created_at
"""

CONFIRM_EMAIL_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px">
  <h2 style="color:#1a56db">✅ Anmeldung erhalten</h2>
  <p>Vielen Dank, <b>{{ $('Parse: Form Fields').item.json.school_name }}</b>!</p>
  <p>Wir haben Ihre Anfrage für den Kurs <b>{{ $('Parse: Form Fields').item.json.course_name }}</b> erhalten
  und melden uns innerhalb von 24 Stunden.</p>
  <table style="border-collapse:collapse;margin-top:16px">
    <tr><td style="padding:4px 12px;color:#555">Einrichtung:</td>
        <td style="padding:4px 12px"><b>{{ $('Parse: Form Fields').item.json.school_name }}</b></td></tr>
    <tr><td style="padding:4px 12px;color:#555">Kurs:</td>
        <td style="padding:4px 12px"><b>{{ $('Parse: Form Fields').item.json.course_name }}</b></td></tr>
    <tr><td style="padding:4px 12px;color:#555">Eingegangen:</td>
        <td style="padding:4px 12px">{{ new Date().toLocaleString('de-DE') }}</td></tr>
  </table>
  <p style="margin-top:24px;color:#555">Mit freundlichen Grüßen<br>
  <b>Kirill Brüggemann</b><br>kontakt@kibrueg.de</p>
</div>
"""

nodes = [
  # Webhook
  {"id": "n_wh", "name": "Webhook: Onboarding Form",
   "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 300],
   "parameters": {"path": "onboarding-form", "httpMethod": "POST",
                  "responseMode": "responseNode"}},

  # Immediate response (don't block Tally)
  {"id": "n_resp", "name": "Respond: 200 OK",
   "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [220, 460],
   "parameters": {"respondWith": "json",
                  "responseBody": '{"status":"received","message":"Danke! Wir melden uns."}'}},

  # Parse fields
  {"id": "n_parse", "name": "Parse: Form Fields",
   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [220, 300],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": PARSE_JS}},

  # Validate — has school + course
  {"id": "n_if", "name": "IF: Valid Submission",
   "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [440, 300],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c1",
                     "leftValue": "={{ $json.course_name }}", "rightValue": "Unbekannter Kurs",
                     "operator": {"type": "string", "operation": "notEquals", "singleValue": False}}],
     "combinator": "and"}}},

  # Insert to DB
  {"id": "n_db", "name": "DB: Insert Submission",
   "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [660, 220],
   "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "query": INSERT_SQL, "options": {}}},

  # Confirmation email (only if contact_email present)
  {"id": "n_if_email", "name": "IF: Has Email",
   "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [880, 220],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c2",
                     "leftValue": "={{ $('Parse: Form Fields').item.json.contact_email }}",
                     "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  {"id": "n_gmail", "name": "Gmail: Confirm to School",
   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "position": [1100, 140],
   "credentials": GMAIL_CRED,
   "parameters": {
     "operation": "send",
     "sendTo": "={{ $('Parse: Form Fields').item.json.contact_email }}",
     "subject": "Anmeldung erhalten – JobRadar B2B",
     "message": CONFIRM_EMAIL_HTML,
     "options": {"replyTo": "kontakt@kibrueg.de", "bodyContentType": "html"}
   }},

  # Telegram to operator
  {"id": "n_tg", "name": "Telegram: New Submission",
   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1100, 340],
   "parameters": {
     "method": "POST",
     "url": f"https://api.telegram.org/bot{TELEGRAM}/sendMessage",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": (
       "={{ JSON.stringify({"
       "  chat_id: '" + CHAT_ID + "',"
       "  parse_mode: 'HTML',"
       "  text: '\\u{1F4CB} <b>Neue Onboarding-Anfrage</b>\\n'"
       "    + '🏫 ' + $('Parse: Form Fields').item.json.school_name + '\\n'"
       "    + '📚 ' + $('Parse: Form Fields').item.json.course_name + '\\n'"
       "    + '📧 ' + ($('Parse: Form Fields').item.json.contact_email || '—')"
       "}) }}"
     ),
     "options": {}
   }},

  # Also forward submission to own email for review
  {"id": "n_gmail_op", "name": "Gmail: Notify Operator",
   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "position": [1100, 500],
   "credentials": GMAIL_CRED,
   "parameters": {
     "operation": "send",
     "sendTo": "brueggemannkirill@gmail.com",
     "subject": "={{ '[Onboarding] ' + $('Parse: Form Fields').item.json.school_name + ' – ' + $('Parse: Form Fields').item.json.course_name }}",
     "message": "={{ '<pre>' + JSON.stringify($('Parse: Form Fields').item.json, null, 2) + '</pre>' }}",
     "options": {"bodyContentType": "html"}
   }},

  # Invalid submission — log only
  {"id": "n_noop", "name": "Skip: Invalid",
   "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [660, 400], "parameters": {}},
]

def c(dst, idx=0):
    return {"node": dst, "type": "main", "index": idx}

connections = {
  "Webhook: Onboarding Form": {"main": [[c("Respond: 200 OK"), c("Parse: Form Fields")]]},
  "Parse: Form Fields":       {"main": [[c("IF: Valid Submission")]]},
  "IF: Valid Submission":     {"main": [[c("DB: Insert Submission")], [c("Skip: Invalid")]]},
  "DB: Insert Submission":    {"main": [[c("IF: Has Email"), c("Telegram: New Submission")]]},
  "IF: Has Email":            {"main": [[c("Gmail: Confirm to School"), c("Gmail: Notify Operator")], [c("Gmail: Notify Operator")]]},
}

wf = req("POST", "/api/v1/workflows", {
    "name": "JobRadar -- Flow 19: Course Onboarding Webhook",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
})
wid = wf["id"]
print(f"Created Flow 19 (ID: {wid})")

r = req("POST", f"/api/v1/workflows/{wid}/activate")
print(f"Active: {r.get('active')}")
print(f"\nWebhook URL: {N8N_BASE}/webhook/onboarding-form")
print("\nTally → Settings → Webhooks → add this URL")
print("Flat JSON test:")
print('  curl -X POST /webhook/onboarding-form \\')
print('    -H "Content-Type: application/json" \\')
print('    -d \'{"school_name":"Test GmbH","contact_email":"test@test.de","course_name":"IT-Umschulung"}\'')
