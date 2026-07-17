"""
Create Flow 16: B2B Course Matching.
Daily 05:30: queue new jobs (3-day window, prospecting rows excluded) ->
drain queue via scraper-agent /match-b2b (rule-based, local, no LLM cost) ->
Telegram summary. Env: N8N_API_KEY, N8N_BASE.
"""
import json, os, ssl, urllib.request

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
PG_CRED = {"postgres": {"id": "Tvuhat51UDCzKwnE", "name": "Postgres account"}}

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, context=CTX) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {path}: {e.read().decode()[:400]}")

existing = [w for w in req("GET", "/api/v1/workflows?limit=100")["data"]
            if w["name"].startswith("JobRadar -- Flow 16")]
if existing:
    raise SystemExit(f"Flow 16 already exists: {existing[0]['id']} — not overwriting.")

SUMMARIZE_JS = """const items = $input.all();
let jobs = 0, matches = 0, errors = 0;
for (const it of items) {
  const j = it.json;
  if (j.error || j.matches === undefined) { errors++; continue; }
  jobs++;
  matches += (j.matches || 0);
}
const now = new Date().toISOString().slice(0, 16).replace('T', ' ');
const text = `\\u{1F3EB} <b>B2B Matching</b> [${now}]\\n` +
  `Jobs verarbeitet: ${jobs}\\nMatches erstellt: ${matches}` +
  (errors ? `\\n\\u26A0\\uFE0F Fehler: ${errors}` : '');
return [{ json: { text, jobs, matches, errors } }];"""

nodes = [
  {"id": "n_schedule", "name": "Schedule: Daily 05:30", "type": "n8n-nodes-base.scheduleTrigger",
   "typeVersion": 1.2, "position": [200, 300],
   "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "30 5 * * *"}]}}},

  {"id": "n_manual", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger",
   "typeVersion": 1, "position": [200, 480], "parameters": {}},

  {"id": "n_queue", "name": "DB: Queue New Jobs", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [420, 300], "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "options": {}, "query":
"""INSERT INTO matching_queue (job_id)
SELECT j.id FROM jobs j
WHERE j.created_at >= NOW() - INTERVAL '3 days'
  AND j.job_title NOT LIKE 'Prospecting:%'
  AND NOT EXISTS (SELECT 1 FROM job_matches m WHERE m.job_id = j.id)
ON CONFLICT (job_id) DO NOTHING;
SELECT job_id::text AS job_id FROM matching_queue ORDER BY added_at LIMIT 200;"""}},

  {"id": "n_if", "name": "IF: Queue Not Empty", "type": "n8n-nodes-base.if",
   "typeVersion": 2, "position": [640, 300],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c1", "leftValue": "={{ $json.job_id }}", "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  {"id": "n_match", "name": "Agent: Match Job", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [860, 240], "onError": "continueErrorOutput",
   "parameters": {"method": "POST", "url": "http://scraper-agent:8200/match-b2b",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({ job_id: $json.job_id }) }}",
     "sendHeaders": True,
     "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
     "options": {"timeout": 30000,
                 "batching": {"batch": {"batchSize": 1, "batchInterval": 250}}}}},

  {"id": "n_summary", "name": "Summarize", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1080, 300],
   "parameters": {"mode": "runOnceForAllItems", "jsCode": SUMMARIZE_JS}},

  {"id": "n_telegram", "name": "Telegram: Summary", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [1300, 300],
   "parameters": {"method": "POST",
     "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({ chat_id: '-1004436898733', parse_mode: 'HTML', text: $json.text }) }}",
     "sendHeaders": True,
     "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
     "options": {}}},

  {"id": "n_noop", "name": "Queue Empty", "type": "n8n-nodes-base.noOp",
   "typeVersion": 1, "position": [860, 460], "parameters": {}},
]

connections = {
  "Schedule: Daily 05:30": {"main": [[{"node": "DB: Queue New Jobs", "type": "main", "index": 0}]]},
  "Manual Trigger":        {"main": [[{"node": "DB: Queue New Jobs", "type": "main", "index": 0}]]},
  "DB: Queue New Jobs":    {"main": [[{"node": "IF: Queue Not Empty", "type": "main", "index": 0}]]},
  "IF: Queue Not Empty":   {"main": [
      [{"node": "Agent: Match Job", "type": "main", "index": 0}],
      [{"node": "Queue Empty", "type": "main", "index": 0}]]},
  "Agent: Match Job":      {"main": [
      [{"node": "Summarize", "type": "main", "index": 0}],
      [{"node": "Summarize", "type": "main", "index": 0}]]},
  "Summarize":             {"main": [[{"node": "Telegram: Summary", "type": "main", "index": 0}]]},
}

wf = req("POST", "/api/v1/workflows", {
    "name": "JobRadar -- Flow 16: B2B Course Matching",
    "nodes": nodes, "connections": connections,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}})
wid = wf["id"]
print("created:", wid)
r = req("POST", f"/api/v1/workflows/{wid}/activate")
print("active:", r.get("active"))
