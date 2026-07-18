"""
Create Flow 17: Praktikum Outreach (Weiterbildung + Hermes leads).
Two independent subgraphs in one workflow:
  A) Cron 08:00 → DB (Weiterbildung schools from GS pool with emails) → LLM → Gmail
  B) Webhook → Hermes lead prep → LLM → Gmail
Both log to DB and send Telegram. Anti-spam: 30-day cooldown per email.
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
            if w["name"].startswith("JobRadar -- Flow 17")]
if existing:
    raise SystemExit(f"Flow 17 already exists: {existing[0]['id']}")

PG_CRED     = {"postgres":  {"id": os.environ.get("N8N_CRED_POSTGRES", "Tvuhat51UDCzKwnE"), "name": "Postgres account"}}
GMAIL_CRED  = {"gmailOAuth2": {"id": os.environ.get("N8N_CRED_GMAIL",    "7rf7G4mjBXt01V7T"), "name": "Gmail"}}
TELEGRAM    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID     = "-1004436898733"
MODEL       = "qwen/qwen3-30b-a3b-instruct-2507"

SYSTEM_PROMPT = (
    "Du schreibst kurze, direkte Bewerbungs-E-Mails auf Deutsch für Kirill Brüggemann. "
    "Kirill ist ein Junior KI-Automatisierungs- und Backend-Entwickler aus Berlin. "
    "Skills: Python, n8n, Make.com, REST API, LLMs, PostgreSQL, Telegram-Bots. "
    "Er sucht ein bezahltes Praktikum oder eine Einstiegsposition (100% remote). "
    "Er ist deutscher Staatsbürger, C1 Deutsch, B2 Englisch. "
    "Stil: direkt, bescheiden aber konkret. Länge: max 5 Sätze. "
    "Für Weiterbildungseinrichtungen: frage nach Praktikumsmöglichkeiten im Bereich KI/Automatisierung, "
    "Content Creation, Datenerfassung/Web-Scraping, SAP oder UI/UX-Prototypen, "
    "direkt oder über Unternehmenspartner. "
    "Gib NUR den E-Mail-Text zurück. Format:\\nBetreff: [Betreff]\\n\\n[Nachrichtentext]\\n\\n"
    "Viele Grüße\\nKirill Brüggemann\\nbrueggemannkirill@gmail.com"
)

GS_QUERY = """
SELECT DISTINCT ON (j.contact_email)
  j.company, j.contact_email, j.source_url, j.city
FROM jobs j
WHERE j.contact_email IS NOT NULL
  AND j.contact_email != ''
  AND j.source_url ILIKE '%gelbeseiten%'
  AND (
    j.source_url ILIKE '%weiterbildung%'
    OR j.source_url ILIKE '%bildungsinstitut%'
    OR j.source_url ILIKE '%erwachsenenbildung%'
    OR j.source_url ILIKE '%edv-schulungen%'
    OR j.source_url ILIKE '%sprachschule%'
    OR j.source_url ILIKE '%berufliche-weiterbildung%'
    OR j.source_url ILIKE '%umschulung%'
    OR j.source_url ILIKE '%nachhilfe%'
    OR j.source_url ILIKE '%seminar%'
    OR j.source_url ILIKE '%coaching%'
  )
  AND NOT EXISTS (
    SELECT 1 FROM job_events je
    WHERE je.raw_text ILIKE '%outreach_sent%'
      AND je.raw_text ILIKE '%' || j.contact_email || '%'
      AND je.created_at > NOW() - INTERVAL '30 days'
  )
ORDER BY j.contact_email, j.created_at DESC
LIMIT 5
"""

LOG_QUERY = """
INSERT INTO job_events (job_id, event_type, raw_text, created_at)
SELECT j.id, 'outreach_sent',
  'outreach_sent to=' || $1 || ' company=' || $2,
  NOW()
FROM jobs j WHERE j.contact_email = $1 LIMIT 1
ON CONFLICT DO NOTHING
"""

PARSE_JS = """
const item = $input.item;
let raw = "";
try {
  raw = item.json.choices[0].message.content
    .replace(/<think>[\\s\\S]*?<\\/think>/g, "").trim();
} catch(e) { return { json: { _skip: true } }; }

const lines = raw.split("\\n");
let subject = "", body = "";
for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith("Betreff:")) {
    subject = lines[i].replace("Betreff:", "").trim();
  } else if (subject && lines[i].trim()) {
    body = lines.slice(i).join("\\n").trim();
    break;
  }
}
if (!subject) subject = "Anfrage: Bezahltes Praktikum KI-Automatisierung";
return { json: { ...item.json, email_subject: subject, email_body: body } };
"""

HERMES_PREP_JS = """
const b = $json.body || $json;
return { json: {
  company:       b.company   || "Unbekannte Firma",
  contact_email: b.email     || "",
  source_url:    b.url       || "",
  city:          b.city      || "",
  job_title:     b.job_title || "",
  lead_type:     b.type      || "job"
}};
"""

def llm_node(nid, name, pos, company_expr, url_expr, city_expr):
    user_msg = (
        "={{ 'Firma: ' + " + company_expr + " + '\\nWebsite: ' + (" + url_expr + " || 'unbekannt')"
        " + '\\nOrt: ' + (" + city_expr + " || 'unbekannt')"
        " + '\\n\\nSchreib eine kurze E-Mail für ein bezahltes Praktikum im Bereich KI-Automatisierung.' }}"
    )
    return {
        "id": nid, "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": pos,
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization",
                 "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"},
                {"name": "HTTP-Referer",
                 "value": "https://jobradar.kibrueg.de"},
                {"name": "X-Title", "value": "JobRadar Outreach"}
            ]},
            "sendBody": True, "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({"
                "  model: '" + MODEL + "',"
                "  temperature: 0.4,"
                "  messages: ["
                "    { role: 'system', content: `" + SYSTEM_PROMPT.replace("`", "'") + "` },"
                "    { role: 'user', content: " + user_msg[4:-3] + " }"
                "  ]"
                "}) }}"
            ),
            "options": {"timeout": 30000}
        }
    }


def gmail_send(nid, name, pos, to_expr, subj_expr, body_expr):
    return {
        "id": nid, "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1, "position": pos,
        "credentials": GMAIL_CRED,
        "parameters": {
            "operation": "send",
            "sendTo": to_expr,
            "subject": subj_expr,
            "message": body_expr,
            "options": {"replyTo": "brueggemannkirill@gmail.com"}
        }
    }


def pg_log(nid, name, pos, email_expr, company_expr):
    return {
        "id": nid, "name": name,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5, "position": pos,
        "credentials": PG_CRED,
        "parameters": {
            "operation": "executeQuery",
            "query": LOG_QUERY,
            "options": {},
            "additionalFields": {
                "queryParams": "={{ [" + email_expr + ", " + company_expr + "] }}"
            }
        }
    }


def tg_node(nid, name, pos):
    return {
        "id": nid, "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": pos,
        "parameters": {
            "method": "POST",
            "url": f"https://api.telegram.org/bot{TELEGRAM}/sendMessage",
            "sendBody": True, "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({"
                "  chat_id: '" + CHAT_ID + "',"
                "  parse_mode: 'HTML',"
                "  text: '\\u{1F4E7} Outreach gesendet\\n<b>' + $json.company + '</b>\\n'"
                "    + $json.contact_email + '\\nBetreff: ' + $json.email_subject"
                "}) }}"
            ),
            "options": {}
        }
    }


# ── Node list ─────────────────────────────────────────────────────────────────
nodes = [
  # ── BRANCH A: Cron (Weiterbildung DB) ──
  {"id": "a_cron", "name": "A: Schedule 08:00",
   "type": "n8n-nodes-base.scheduleTrigger",
   "typeVersion": 1.2, "position": [0, 0],
   "parameters": {"rule": {"interval": [{"field": "cronExpression",
                                         "expression": "0 8 * * *"}]}}},

  {"id": "a_db", "name": "A: DB Weiterbildung Leads",
   "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [220, 0],
   "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "query": GS_QUERY, "options": {}}},

  {"id": "a_if", "name": "A: IF Has Leads",
   "type": "n8n-nodes-base.if",
   "typeVersion": 2, "position": [440, 0],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c1",
                     "leftValue": "={{ $json.contact_email }}",
                     "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  llm_node("a_llm", "A: LLM Generate Email", [660, -60],
           "$json.company", "$json.source_url", "$json.city"),

  {"id": "a_parse", "name": "A: Parse LLM Response",
   "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [880, -60],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": PARSE_JS}},

  gmail_send("a_gmail", "A: Gmail Send",
             [1100, -60],
             "={{ $json.contact_email }}",
             "={{ $json.email_subject }}",
             "={{ $json.email_body }}"),

  pg_log("a_log", "A: DB Log Sent", [1320, -60],
         "$json.contact_email", "$json.company || 'unknown'"),

  tg_node("a_tg", "A: Telegram Sent", [1540, -60]),

  # ── BRANCH B: Hermes Webhook ──
  {"id": "b_wh", "name": "B: Hermes Webhook",
   "type": "n8n-nodes-base.webhook",
   "typeVersion": 2, "position": [0, 300],
   "parameters": {"path": "hermes-outreach-lead",
                  "httpMethod": "POST",
                  "responseMode": "responseNode"}},

  {"id": "b_resp", "name": "B: Webhook Respond",
   "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [220, 400],
   "parameters": {"respondWith": "json", "responseBody": '{"status":"queued"}'}},

  {"id": "b_prep", "name": "B: Prep Lead",
   "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [220, 220],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": HERMES_PREP_JS}},

  {"id": "b_if", "name": "B: IF Has Email",
   "type": "n8n-nodes-base.if",
   "typeVersion": 2, "position": [440, 220],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c2",
                     "leftValue": "={{ $json.contact_email }}",
                     "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  llm_node("b_llm", "B: LLM Generate Email", [660, 160],
           "$json.company", "$json.source_url", "$json.city"),

  {"id": "b_parse", "name": "B: Parse LLM Response",
   "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [880, 160],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": PARSE_JS}},

  gmail_send("b_gmail", "B: Gmail Send",
             [1100, 160],
             "={{ $json.contact_email }}",
             "={{ $json.email_subject }}",
             "={{ $json.email_body }}"),

  pg_log("b_log", "B: DB Log Sent", [1320, 160],
         "$json.contact_email", "$json.company || 'unknown'"),

  tg_node("b_tg", "B: Telegram Sent", [1540, 160]),
]

# ── Connections (use display names as keys) ───────────────────────────────────
def c(dst, idx=0):
    return {"node": dst, "type": "main", "index": idx}

connections = {
  "A: Schedule 08:00":          {"main": [[c("A: DB Weiterbildung Leads")]]},
  "A: DB Weiterbildung Leads":  {"main": [[c("A: IF Has Leads")]]},
  "A: IF Has Leads":            {"main": [[c("A: LLM Generate Email")], []]},
  "A: LLM Generate Email":      {"main": [[c("A: Parse LLM Response")]]},
  "A: Parse LLM Response":      {"main": [[c("A: Gmail Send")]]},
  "A: Gmail Send":              {"main": [[c("A: DB Log Sent"), c("A: Telegram Sent")]]},

  "B: Hermes Webhook":          {"main": [[c("B: Webhook Respond"), c("B: Prep Lead")]]},
  "B: Prep Lead":               {"main": [[c("B: IF Has Email")]]},
  "B: IF Has Email":            {"main": [[c("B: LLM Generate Email")], []]},
  "B: LLM Generate Email":      {"main": [[c("B: Parse LLM Response")]]},
  "B: Parse LLM Response":      {"main": [[c("B: Gmail Send")]]},
  "B: Gmail Send":              {"main": [[c("B: DB Log Sent"), c("B: Telegram Sent")]]},
}

wf = req("POST", "/api/v1/workflows", {
    "name": "JobRadar -- Flow 17: Praktikum Outreach",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
})
wid = wf["id"]
print(f"Created Flow 17 (ID: {wid})")

r = req("POST", f"/api/v1/workflows/{wid}/activate")
print(f"Active: {r.get('active')}")
print(f"Webhook: {N8N_BASE}/webhook/hermes-outreach-lead")
print()
print("Hermes POST format:")
print('  POST /webhook/hermes-outreach-lead')
print('  {"company":"Name","email":"x@y.de","url":"https://...","city":"Berlin","job_title":"...","type":"praktikum"}')
