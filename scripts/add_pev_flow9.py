"""
Add Plan-Execute-Verify pre-flight check to Flow 9 (Universal Outreach).
Inserts between Build Personalized Email and Gmail: Send:
  PEV: Pre-flight Check → IF: PEV Pass?
      YES → Gmail: Send (existing)
      NO  → PEV: Log Blocked
"""
import json, os, urllib.request, ssl, sys

API_KEY = os.environ["N8N_API_KEY"]
BASE = "https://n8n.157.180.112.46.sslip.io"
FLOW_ID = "tv434oBgRQrUhqAe"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wf = req("GET", f"/api/v1/workflows/{FLOW_ID}")
print(f"Fetched Flow 9: {len(wf['nodes'])} nodes")

PREFLIGHT_JS = r"""const item = $input.item.json;
const issues = [];

// Plan: validate before executing send
const to = item.to || '';
if (!to || !to.includes('@') || to.trim().length < 5) {
  issues.push('invalid_recipient:' + to.substring(0, 50));
}

const body = item.body || '';
const subject = item.subject || '';

// Check for unfilled template placeholders
const placeholderRe = /\{\{[^}]+\}\}|\[PLACEHOLDER[^\]]*\]|\[DEIN [^\]]+\]|\[YOUR [^\]]+\]/gi;
if (placeholderRe.test(body)) issues.push('body_has_placeholders');
if (placeholderRe.test(subject)) issues.push('subject_has_placeholders');

// Content completeness
if (body.trim().length < 80) issues.push('body_too_short:' + body.trim().length + 'chars');
if (!subject || subject.trim().length < 4) issues.push('subject_empty');

// Avoid obvious noreply/invalid addresses
const noSendRe = /noreply|no-reply|donotreply|mailer-daemon|postmaster|bounce/i;
if (noSendRe.test(to)) issues.push('recipient_is_noreply');

return [{ json: { ...item, pev_ok: issues.length === 0, pev_issues: issues.join('; ') || 'none' } }];"""

LOG_BLOCKED_JS = r"""return [{ json: {
  blocked_at: new Date().toISOString(),
  company: $json.company_name || $json.company_id || '?',
  to: $json.to || '?',
  subject: $json.subject || '?',
  issues: $json.pev_issues,
  action: 'pev_blocked_pre_send'
} }];"""

new_nodes = [
    {
        "id": "n_pev_check",
        "name": "PEV: Pre-flight Check",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [710, 240],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": PREFLIGHT_JS}
    },
    {
        "id": "n_pev_if",
        "name": "IF: PEV Pass?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [820, 420],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{
                    "id": "pev_pass",
                    "leftValue": "={{ $json.pev_ok }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}
                }],
                "combinator": "and"
            },
            "options": {}
        }
    },
    {
        "id": "n_pev_log",
        "name": "PEV: Log Blocked",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1040, 520],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": LOG_BLOCKED_JS}
    }
]

# Patch connections:
# Remove: Build Personalized Email → Gmail: Send
# Add:    Build Personalized Email → PEV: Pre-flight Check → IF: PEV Pass?
#         IF: PEV Pass? YES → Gmail: Send  (existing node, just redirect)
#         IF: PEV Pass? NO  → PEV: Log Blocked
conns = wf["connections"]

# Reroute Build Personalized Email output to pre-flight
conns["Build Personalized Email"] = {
    "main": [[{"node": "PEV: Pre-flight Check", "type": "main", "index": 0}]]
}

conns["PEV: Pre-flight Check"] = {
    "main": [[{"node": "IF: PEV Pass?", "type": "main", "index": 0}]]
}

conns["IF: PEV Pass?"] = {
    "main": [
        [{"node": "Gmail: Send", "type": "main", "index": 0}],   # YES → send
        [{"node": "PEV: Log Blocked", "type": "main", "index": 0}]  # NO → block
    ]
}

put_body = {
    "name": wf["name"],
    "nodes": wf["nodes"] + new_nodes,
    "connections": conns,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
}
data = json.dumps(put_body).encode()
r = urllib.request.Request(f"{BASE}/api/v1/workflows/{FLOW_ID}", data=data,
    headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method="PUT")
try:
    with urllib.request.urlopen(r, context=CTX) as resp:
        result = json.loads(resp.read())
        pev_nodes = [n["name"] for n in result["nodes"] if "PEV" in n["name"]]
        print(f"SUCCESS! Total nodes: {len(result['nodes'])}")
        print(f"PEV nodes: {pev_nodes}")
        # Verify Build Personalized Email → PEV
        bpe_conn = result["connections"].get("Build Personalized Email", {}).get("main", [])
        print(f"Build Email -> {bpe_conn[0][0]['node'] if bpe_conn and bpe_conn[0] else 'EMPTY'}")
        # Verify IF: PEV Pass? connections
        pev_if = result["connections"].get("IF: PEV Pass?", {}).get("main", [])
        print(f"PEV YES -> {pev_if[0][0]['node'] if len(pev_if) > 0 and pev_if[0] else '?'}")
        print(f"PEV NO  -> {pev_if[1][0]['node'] if len(pev_if) > 1 and pev_if[1] else '?'}")
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)
