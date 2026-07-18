"""
Create Flow 18: Weekly B2B Report.
Monday 07:00: for each active school → aggregate pending job_matches (last 7 days, fit_score>=40)
→ insert into reports → email report_recipients → Telegram if notification_config has chat_id.
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
            if w["name"].startswith("JobRadar -- Flow 18")]
if existing:
    raise SystemExit(f"Flow 18 already exists: {existing[0]['id']}")

PG_CRED    = {"postgres": {"id": os.environ.get("N8N_CRED_POSTGRES", "Tvuhat51UDCzKwnE"),
                            "name": "Postgres account"}}
GMAIL_CRED = {"gmailOAuth2": {"id": os.environ.get("N8N_CRED_GMAIL", "7rf7G4mjBXt01V7T"),
                               "name": "Gmail"}}
TELEGRAM   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = "-1004436898733"

# ── SQL ────────────────────────────────────────────────────────────────────────
QUERY_MATCHES = """
SELECT
  s.id            AS school_id,
  s.name          AS school_name,
  s.notification_config,
  c.id            AS course_id,
  c.title         AS course_title,
  c.target_job_title,
  COUNT(m.id)           AS total_matches,
  AVG(m.fit_score)::int AS avg_score,
  MAX(m.fit_score)      AS max_score,
  COUNT(m.id) FILTER (WHERE m.fit_score >= 60) AS strong_matches,
  jsonb_agg(
    jsonb_build_object(
      'job_title',     j.job_title,
      'company',       j.company,
      'location',      j.location,
      'fit_score',     m.fit_score,
      'matched_skills', m.matched_skills,
      'missing_skills', m.missing_skills
    ) ORDER BY m.fit_score DESC
  ) FILTER (WHERE m.fit_score >= 40) AS top_matches
FROM job_matches m
JOIN schools  s ON s.id = m.school_id
JOIN courses  c ON c.id = m.course_id
JOIN jobs     j ON j.id = m.job_id
WHERE s.active = true
  AND m.created_at >= NOW() - INTERVAL '7 days'
  AND m.fit_score >= 40
GROUP BY s.id, s.name, s.notification_config, c.id, c.title, c.target_job_title
HAVING COUNT(m.id) > 0
ORDER BY s.name, avg_score DESC
"""

INSERT_REPORT = """
INSERT INTO reports (school_id, course_id, period_start, period_end, report_type, status, summary)
VALUES (
  '{{ $json.school_id }}'::uuid,
  '{{ $json.course_id }}'::uuid,
  (NOW() - INTERVAL '7 days')::date,
  NOW()::date,
  'weekly',
  'ready',
  '{{ JSON.stringify({
    total_matches:   $json.total_matches,
    avg_score:       $json.avg_score,
    strong_matches:  $json.strong_matches,
    generated_at:    new Date().toISOString()
  }) }}'::jsonb
)
ON CONFLICT DO NOTHING
RETURNING id
"""

QUERY_RECIPIENTS = """
SELECT r.email, r.role
FROM report_recipients r
WHERE r.school_id = '{{ $json.school_id }}'::uuid
  AND (r.course_id IS NULL OR r.course_id = '{{ $json.course_id }}'::uuid)
  AND r.active = true
"""

# ── JS helpers ─────────────────────────────────────────────────────────────────
FORMAT_EMAIL_JS = r"""
const m = $json;
const matches = (m.top_matches || []).slice(0, 10);

let rows = matches.map((x, i) => {
  const skills = (x.matched_skills || []).slice(0, 3).join(', ') || '—';
  const miss   = (x.missing_skills || []).slice(0, 2).join(', ') || '—';
  return `<tr>
    <td style="padding:6px 10px">${i+1}</td>
    <td style="padding:6px 10px"><b>${x.job_title || '?'}</b><br><small>${x.company || ''}, ${x.location || ''}</small></td>
    <td style="padding:6px 10px;text-align:center"><b>${x.fit_score}</b></td>
    <td style="padding:6px 10px;font-size:12px">${skills}</td>
    <td style="padding:6px 10px;font-size:12px;color:#888">${miss}</td>
  </tr>`;
}).join('');

const period_end   = new Date().toLocaleDateString('de-DE');
const period_start = new Date(Date.now() - 7*86400000).toLocaleDateString('de-DE');

const html = `
<div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
  <h2 style="color:#1a56db">📊 Wöchentlicher Job-Match-Report</h2>
  <p><b>Kurs:</b> ${m.course_title} (${m.target_job_title || ''})<br>
     <b>Zeitraum:</b> ${period_start} – ${period_end}</p>
  <table style="border-collapse:collapse;width:100%;background:#f9fafb">
    <tr style="background:#1a56db;color:white">
      <th style="padding:8px 10px">#</th>
      <th style="padding:8px 10px">Stelle</th>
      <th style="padding:8px 10px">Score</th>
      <th style="padding:8px 10px">Match-Skills</th>
      <th style="padding:8px 10px">Fehlende Skills</th>
    </tr>
    ${rows}
  </table>
  <p style="margin-top:16px;color:#555">
    Gesamt: <b>${m.total_matches}</b> Matches · Ø Score: <b>${m.avg_score}</b> ·
    Starke Matches (≥60): <b>${m.strong_matches}</b>
  </p>
  <p style="font-size:11px;color:#aaa">JobRadar B2B — automatisch generiert</p>
</div>`;

return { json: { ...m, email_html: html,
  email_subject: `JobRadar Report: ${m.course_title} (${period_start}–${period_end})` }};
"""

TG_FORMAT_JS = r"""
const m = $json;
const cfg = m.notification_config || {};
const chat_id = cfg.telegram_chat_id;
if (!chat_id) return [];   // no Telegram config → skip

const top3 = (m.top_matches || []).slice(0, 3)
  .map(x => `  • ${x.job_title} @ ${x.company} (${x.fit_score})`).join('\n');

const text = `📊 <b>Weekly Report</b>\n` +
  `Kurs: ${m.course_title}\n` +
  `Matches: ${m.total_matches} | Ø ${m.avg_score} | Stark: ${m.strong_matches}\n\n` +
  `Top 3:\n${top3}`;

return [{ json: { chat_id, text } }];
"""

# ── Nodes ──────────────────────────────────────────────────────────────────────
nodes = [
  {"id": "n_cron", "name": "Schedule: Monday 07:00",
   "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 300],
   "parameters": {"rule": {"interval": [{"field": "cronExpression",
                                         "expression": "0 7 * * 1"}]}}},

  {"id": "n_manual", "name": "Manual Trigger",
   "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 500],
   "parameters": {}},

  {"id": "n_matches", "name": "DB: Get Weekly Matches",
   "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [220, 300],
   "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "query": QUERY_MATCHES, "options": {}}},

  {"id": "n_if", "name": "IF: Has Matches",
   "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [440, 300],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c1",
                     "leftValue": "={{ $json.school_id }}", "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  {"id": "n_noop", "name": "No Matches This Week",
   "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [640, 480], "parameters": {}},

  {"id": "n_insert", "name": "DB: Insert Report",
   "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [640, 300],
   "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "query": INSERT_REPORT, "options": {}}},

  {"id": "n_format", "name": "Format: Email HTML",
   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [860, 300],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": FORMAT_EMAIL_JS}},

  {"id": "n_recipients", "name": "DB: Get Recipients",
   "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [1080, 300],
   "credentials": PG_CRED,
   "parameters": {"operation": "executeQuery", "query": QUERY_RECIPIENTS, "options": {}}},

  {"id": "n_if_email", "name": "IF: Has Recipients",
   "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [1300, 300],
   "parameters": {"conditions": {
     "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"id": "c2",
                     "leftValue": "={{ $json.email }}", "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},

  {"id": "n_gmail", "name": "Gmail: Send Report",
   "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "position": [1520, 220],
   "credentials": GMAIL_CRED,
   "parameters": {
     "operation": "send",
     "sendTo": "={{ $json.email }}",
     "subject": "={{ $('Format: Email HTML').item.json.email_subject }}",
     "message": "={{ $('Format: Email HTML').item.json.email_html }}",
     "options": {
       "replyTo": "kontakt@kibrueg.de",
       "appendAttribution": False,
       "bodyContentType": "html"
     }
   }},

  {"id": "n_tg_fmt", "name": "Format: Telegram",
   "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1080, 480],
   "parameters": {"mode": "runOnceForEachItem", "jsCode": TG_FORMAT_JS}},

  {"id": "n_tg_send", "name": "Telegram: Send Report",
   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1300, 480],
   "parameters": {
     "method": "POST",
     "url": f"https://api.telegram.org/bot{TELEGRAM}/sendMessage",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({ chat_id: $json.chat_id, parse_mode: 'HTML', text: $json.text }) }}",
     "options": {}
   }},

  # Operator summary to owner Telegram
  {"id": "n_summary", "name": "Telegram: Operator Summary",
   "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1520, 400],
   "parameters": {
     "method": "POST",
     "url": f"https://api.telegram.org/bot{TELEGRAM}/sendMessage",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": (
       "={{ JSON.stringify({"
       "  chat_id: '" + CHAT_ID + "',"
       "  parse_mode: 'HTML',"
       "  text: '\\u{1F4CA} <b>Flow 18 Report done</b>\\n'"
       "    + $('DB: Get Weekly Matches').item.json.school_name + ' — '"
       "    + $('DB: Get Weekly Matches').item.json.course_title + '\\n'"
       "    + $('DB: Get Weekly Matches').item.json.total_matches + ' matches'"
       "}) }}"
     ),
     "options": {}
   }},
]

def c(dst, idx=0):
    return {"node": dst, "type": "main", "index": idx}

connections = {
  "Schedule: Monday 07:00": {"main": [[c("DB: Get Weekly Matches")]]},
  "Manual Trigger":          {"main": [[c("DB: Get Weekly Matches")]]},
  "DB: Get Weekly Matches":  {"main": [[c("IF: Has Matches")]]},
  "IF: Has Matches":         {"main": [
      [c("DB: Insert Report")],
      [c("No Matches This Week")]
  ]},
  "DB: Insert Report":       {"main": [[c("Format: Email HTML")]]},
  "Format: Email HTML":      {"main": [[c("DB: Get Recipients"), c("Format: Telegram")]]},
  "DB: Get Recipients":      {"main": [[c("IF: Has Recipients")]]},
  "IF: Has Recipients":      {"main": [
      [c("Gmail: Send Report")],
      []
  ]},
  "Gmail: Send Report":      {"main": [[c("Telegram: Operator Summary")]]},
  "Format: Telegram":        {"main": [[c("Telegram: Send Report")]]},
}

wf = req("POST", "/api/v1/workflows", {
    "name": "JobRadar -- Flow 18: Weekly B2B Report",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
})
wid = wf["id"]
print(f"Created Flow 18 (ID: {wid})")

r = req("POST", f"/api/v1/workflows/{wid}/activate")
print(f"Active: {r.get('active')}")
print("Runs: Monday 07:00 | Manual trigger available")
print("\nTo add report recipient for Demo Akademie:")
print("INSERT INTO report_recipients (school_id, email, role)")
print("SELECT id, 'your@email.de', 'coach' FROM schools WHERE name LIKE '%Demo%';")
