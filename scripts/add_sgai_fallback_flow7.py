"""
Add Scraper-Agent fallback to Flow 7 (SERP).
When SGai: Scrape hits monthly limit → error output → Backup: HTTP Fetch
(self-hosted scraper-agent on :8200) → Backup: LLM Extract → Backup: Parse
→ same downstream as SGai success path.

Requires scraper-agent service running on VPS at localhost:8200.
"""
import json, os, urllib.request, ssl, sys

API_KEY = os.environ["N8N_API_KEY"]
BASE = "https://n8n.157.180.112.46.sslip.io"
FLOW_ID = "VBfS8H71yz0ArkWT"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wf = req("GET", f"/api/v1/workflows/{FLOW_ID}")
print(f"Fetched Flow 7: {len(wf['nodes'])} nodes")

# Find what node SGai: Scrape success path goes to (to wire our fallback to the same destination)
conns = wf["connections"]
sgai_conn = conns.get("SGai: Scrape", {})
sgai_success_targets = sgai_conn.get("main", [[]])[0] if sgai_conn.get("main") else []
print(f"SGai: Scrape success -> {[t['node'] for t in sgai_success_targets]}")

# The scraper-agent prompt: extract job listing data from career page
SCRAPER_PROMPT = (
    "Extract all job listings from this career page. "
    "Return a JSON array of objects, each with: "
    "title (job title), url (application/job detail URL), location, work_mode (remote/hybrid/onsite), "
    "tech_stack (array of technologies), summary (1-2 sentences). "
    "If no jobs found, return []."
)

# Parse node: normalize scraper-agent response to same shape as SGai output
BACKUP_PARSE_JS = r"""const item = $input.item.json;
const scraperResult = item.result || item;
// scraper-agent returns { result: [...], url, chars_sent }
const jobs = Array.isArray(scraperResult.result) ? scraperResult.result :
             Array.isArray(scraperResult) ? scraperResult : [];
if (!jobs.length) return [];
return jobs.map(j => ({ json: {
  title: j.title || j.job_title || '',
  url: j.url || j.application_url || item.url || '',
  location: j.location || '',
  work_mode: j.work_mode || j.remote || '',
  tech_stack: Array.isArray(j.tech_stack) ? j.tech_stack : [],
  summary: j.summary || j.description || '',
  _source: 'backup_scraper'
}}));"""

new_nodes = [
    {
        "id": "n_backup_fetch",
        "name": "Backup: HTTP Fetch",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1800, 700],
        "onError": "continueErrorOutput",
        "parameters": {
            "method": "POST",
            "url": "http://scraper-agent:8200/scrape",
            "sendBody": True,
            "contentType": "json",
            "body": {
                "url": "={{ $json.url || $json.source_url || '' }}",
                "prompt": SCRAPER_PROMPT,
                "max_chars": 8000
            },
            "options": {"timeout": 30000}
        }
    },
    {
        "id": "n_backup_parse",
        "name": "Backup: Parse Jobs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2024, 700],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": BACKUP_PARSE_JS}
    }
]

# Wire: SGai: Scrape error output (index 1) → Backup: HTTP Fetch
if "main" not in sgai_conn:
    sgai_conn["main"] = [[], []]
while len(sgai_conn["main"]) < 2:
    sgai_conn["main"].append([])
sgai_conn["main"][1] = [{"node": "Backup: HTTP Fetch", "type": "main", "index": 0}]

# Backup: HTTP Fetch success → Backup: Parse Jobs
# Backup: HTTP Fetch error → nothing (skip silently)
conns["Backup: HTTP Fetch"] = {
    "main": [
        [{"node": "Backup: Parse Jobs", "type": "main", "index": 0}],
        []
    ]
}

# Backup: Parse Jobs → same destination as SGai: Scrape success (if any)
if sgai_success_targets:
    conns["Backup: Parse Jobs"] = {
        "main": [[{"node": t["node"], "type": "main", "index": 0} for t in sgai_success_targets]]
    }
    print(f"Backup: Parse Jobs wired to: {[t['node'] for t in sgai_success_targets]}")
else:
    print("WARNING: SGai: Scrape has no success targets — Backup: Parse Jobs will be terminal")
    conns["Backup: Parse Jobs"] = {"main": [[]]}

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
        backup_nodes = [n["name"] for n in result["nodes"] if n["name"].startswith("Backup:")]
        print(f"SUCCESS! Total nodes: {len(result['nodes'])}")
        print(f"Backup nodes: {backup_nodes}")
        sgai_c = result["connections"].get("SGai: Scrape", {}).get("main", [])
        print(f"SGai error branch -> {sgai_c[1] if len(sgai_c) > 1 else 'EMPTY'}")
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)
