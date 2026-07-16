"""
Add SIGNL4 alerting to JobRadar (two layers, B2B-first):

Layer 1 — System monitoring (global error workflow mdV9VERzHYVcM5vZ):
  Any n8n flow failure → SIGNL4 push via SIGNL4_TEAM_SECRET env var.

Layer 2 — B2B per-school alerting (Flow 11: B2B Matching):
  fit_score ≥ school.notification_config.fit_score_threshold
  → HTTP POST to school's own SIGNL4 webhook (from schools.notification_config).
  Each school configures their own SIGNL4 team in the dashboard — full
  duty scheduling, escalation, and acknowledgment per client.

Architecture: schools.notification_config JSONB holds per-tenant webhook URL.
  n8n reads it from DB → posts to the right endpoint. Zero hardcoded secrets.

Requires:
  N8N_API_KEY in environment
  SIGNL4_TEAM_SECRET in VPS .env  (for system-level monitoring only)
  schools.notification_config.signl4_webhook  (per school, set via DB seed/UI)
"""
import json
import os
import ssl
import sys
import urllib.request

API_KEY         = os.environ["N8N_API_KEY"]
BASE            = os.environ["N8N_BASE"]
ERROR_FLOW_ID   = "mdV9VERzHYVcM5vZ"   # global error workflow

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE


def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())


# ── Layer 1: system monitoring on global error workflow ────────────────────────

def add_system_monitoring():
    wf = req("GET", f"/api/v1/workflows/{ERROR_FLOW_ID}")
    print(f"\n[Layer 1] Error workflow: '{wf['name']}' — {len(wf['nodes'])} nodes")

    if any(n["name"] == "SIGNL4: System Alert" for n in wf["nodes"]):
        print("  Already present — skipping.")
        return

    trigger = next(
        (n for n in wf["nodes"] if "trigger" in n["type"].lower() or "trigger" in n["name"].lower()),
        wf["nodes"][0],
    )
    tx, ty = trigger["position"]

    signl4_node = {
        "id":          "n_signl4_system",
        "name":        "SIGNL4: System Alert",
        "type":        "n8n-nodes-base.httpRequest",
        "typeVersion":  4.2,
        "position":    [tx + 260, ty],
        "onError":     "continueRegularOutput",
        "parameters": {
            "method":      "POST",
            "url":         "=https://connect.signl4.com/webhook/{{ $env.SIGNL4_TEAM_SECRET }}",
            "sendBody":    True,
            "contentType": "json",
            "body": {
                "title":           "=⚠️ n8n Flow Error: {{ $json.workflow?.name || 'unknown' }}",
                "message":         "={{ $json.execution?.error?.message || $json.error?.message || 'No message' }}",
                "severity":        "2",
                "X-S4-ExternalID": "={{ $json.execution?.id || '' }}",
                "X-S4-Status":     "new",
                "X-S4-Service":    "JobRadar-System",
                "workflowId":      "={{ $json.workflow?.id || '' }}",
                "n8nUrl":          f"={BASE}/workflow/{{{{ $json.workflow?.id || '' }}}}",
            },
            "options": {"timeout": 10000},
        },
    }

    conns = wf["connections"]
    tn    = trigger["name"]
    if tn not in conns:
        conns[tn] = {"main": [[]]}
    conns[tn]["main"][0].append({"node": "SIGNL4: System Alert", "type": "main", "index": 0})

    put_body = {"name": wf["name"], "nodes": wf["nodes"] + [signl4_node],
                "connections": conns, "settings": wf.get("settings", {})}
    result = req("PUT", f"/api/v1/workflows/{ERROR_FLOW_ID}", put_body)
    print(f"  Done. Nodes: {len(result['nodes'])}")


# ── Layer 2: per-school B2B match alerting (Flow 11 or standalone flow) ───────
# This creates a standalone "B2B: SIGNL4 Match Alert" flow that gets called
# by Flow 11 (B2B Matching) via n8n Execute Workflow node when score is high.
# Each school's webhook URL comes from schools.notification_config (DB query).

B2B_ALERT_FLOW_NAME = "B2B: SIGNL4 Match Alert"

# JS: reads school's webhook URL from DB result, posts to their SIGNL4 team
ALERT_JS = r"""
// Input: { school_name, course_name, job_title, company, location, fit_score,
//          signl4_webhook, job_url, matched_skills }
const d = $input.item.json;
if (!d.signl4_webhook) {
  return [{ json: { skipped: true, reason: 'no signl4_webhook configured' } }];
}

const body = {
  title:   `🎯 ${d.fit_score}/100 — ${d.job_title}`,
  message: `${d.company} · ${d.location}\nKurs: ${d.course_name}\nSkills: ${(d.matched_skills || []).join(', ')}`,
  severity: d.fit_score >= 85 ? '3' : '2',
  'X-S4-ExternalID': `${d.job_id}_${d.course_id}`,
  'X-S4-Status':     'new',
  'X-S4-Service':    'JobRadar-B2B',
  'X-S4-Link':        d.job_url || '',
  school:  d.school_name,
  course:  d.course_name,
  fitScore: d.fit_score,
};

const r = await $http.post(d.signl4_webhook, body);
return [{ json: { sent: true, school: d.school_name, status: r.status } }];
"""

def add_b2b_alert_flow():
    # Check if flow exists
    flows = req("GET", "/api/v1/workflows?limit=100")
    existing = next(
        (f for f in flows.get("data", []) if f["name"] == B2B_ALERT_FLOW_NAME),
        None,
    )
    if existing:
        print(f"\n[Layer 2] '{B2B_ALERT_FLOW_NAME}' already exists (id={existing['id']}) — skipping.")
        return existing["id"]

    print(f"\n[Layer 2] Creating '{B2B_ALERT_FLOW_NAME}'...")

    nodes = [
        {
            "id": "n_trigger",
            "name": "Execute Workflow Trigger",
            "type": "n8n-nodes-base.executeWorkflowTrigger",
            "typeVersion": 1,
            "position": [240, 300],
            "parameters": {},
        },
        {
            "id": "n_alert",
            "name": "Send SIGNL4 Alert",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [480, 300],
            "parameters": {"mode": "runOnceForEachItem", "jsCode": ALERT_JS},
        },
    ]
    connections = {
        "Execute Workflow Trigger": {
            "main": [[{"node": "Send SIGNL4 Alert", "type": "main", "index": 0}]]
        }
    }
    body = {
        "name":        B2B_ALERT_FLOW_NAME,
        "nodes":       nodes,
        "connections": connections,
        "settings":    {"executionOrder": "v1"},
        "active":      True,
    }
    result = req("POST", "/api/v1/workflows", body)
    flow_id = result["id"]
    print(f"  Created: id={flow_id}")
    print(f"  Call from Flow 11 via 'Execute Workflow' node when fit_score >= threshold.")
    print(f"  Input fields: school_name, course_name, job_title, company, location,")
    print(f"                fit_score, signl4_webhook (from schools.notification_config),")
    print(f"                job_url, matched_skills, job_id, course_id")
    return flow_id


if __name__ == "__main__":
    add_system_monitoring()
    b2b_flow_id = add_b2b_alert_flow()

    print("\n" + "=" * 60)
    print("SIGNL4 integration complete.")
    print()
    print("Checklist:")
    print("  [ ] Add SIGNL4_TEAM_SECRET to VPS .env (system monitoring)")
    print("  [ ] Apply migration 003: db/migrations/003_notification_config.sql")
    print("  [ ] Set notification_config per school in DB:")
    print("      UPDATE schools SET notification_config = '{")
    print('        "signl4_webhook": "https://connect.signl4.com/webhook/SCHOOL_SECRET",')
    print('        "fit_score_threshold": 75,')
    print('        "alert_on_match": true,')
    print('        "weekly_report_email": true')
    print("      }'::jsonb WHERE name = 'Schulname';")
    print(f"  [ ] Wire Flow 11 → Execute Workflow → {B2B_ALERT_FLOW_NAME} (id={b2b_flow_id})")
    print("       when fit_score >= schools.notification_config->>'fit_score_threshold'")
