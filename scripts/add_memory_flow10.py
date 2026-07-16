"""
Add Agent Workflow Memory to Flow 10: cache successful email enrichment patterns.
Before Jina scrape, check if this company's domain has been successfully scraped before.
After successful email find, record the pattern (which sub-page worked).

Nodes added:
1. Before Wait 1.5s: "Memory: Check Domain Cache" (Code) - check if domain pattern known
2. After DB: Save Email: "Memory: Record Pattern" (Code) - save what worked
3. After ReAct: DB Save Email: "Memory: Record Pattern ReAct" (Code) - save sub-page that worked

Memory stored as n8n Static Data (workflow-level key-value store).
"""
import json, os, urllib.request, ssl, sys

API_KEY = os.environ["N8N_API_KEY"]
BASE = os.environ["N8N_BASE"]
FLOW_ID = "C2D45wHhF6sMzTVe"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wf = req("GET", f"/api/v1/workflows/{FLOW_ID}")
print(f"Fetched Flow 10: {len(wf['nodes'])} nodes")

# Memory check: read domain pattern from n8n static data
# n8n static data persists across executions within the same workflow
MEMORY_CHECK_JS = r"""// Agent Workflow Memory: check if we know which sub-page has email for this domain
const item = $input.item.json;
const scrapeUrl = item.scrape_url || item.source_url || '';
let domain = '';
try {
  domain = new URL(scrapeUrl.startsWith('http') ? scrapeUrl : 'https://' + scrapeUrl).hostname;
} catch(e) { domain = ''; }

// Read from workflow static data (persists between runs)
const staticData = $getWorkflowStaticData('global');
const domainCache = staticData.emailDomainCache || {};
const cached = domain ? (domainCache[domain] || null) : null;

return [{ json: {
  ...item,
  mem_domain: domain,
  mem_cached_pattern: cached,  // e.g. '/contact', '/impressum', null
  mem_hint: cached ? 'direct_to_' + cached : 'no_hint'
} }];"""

# Memory record: after successful email find, store which method worked
MEMORY_RECORD_JS = r"""// Agent Workflow Memory: record that the main career page worked
const item = $input.item.json;
const domain = item.mem_domain || '';
if (domain && item.found_email) {
  const staticData = $getWorkflowStaticData('global');
  if (!staticData.emailDomainCache) staticData.emailDomainCache = {};
  staticData.emailDomainCache[domain] = item.scraped_url || 'main';
  // Cap cache at 500 entries to avoid unbounded growth
  const keys = Object.keys(staticData.emailDomainCache);
  if (keys.length > 500) {
    delete staticData.emailDomainCache[keys[0]];
  }
}
return [{ json: item }];"""

MEMORY_RECORD_REACT_JS = r"""// Agent Workflow Memory: record which sub-page (contact/impressum) found email
const item = $input.item.json;
const domain = item.mem_domain || '';
if (domain && item.found_email && item.react_page) {
  const staticData = $getWorkflowStaticData('global');
  if (!staticData.emailDomainCache) staticData.emailDomainCache = {};
  staticData.emailDomainCache[domain] = '/' + item.react_page;
  const keys = Object.keys(staticData.emailDomainCache);
  if (keys.length > 500) {
    delete staticData.emailDomainCache[keys[0]];
  }
}
return [{ json: item }];"""

new_nodes = [
    # Insert before Wait 1.5s (in the IF: Needs Scrape YES branch)
    {
        "id": "n_mem_check",
        "name": "Memory: Check Domain Cache",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [940, 230],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": MEMORY_CHECK_JS}
    },
    # After DB: Save Email (main Jina path)
    {
        "id": "n_mem_record",
        "name": "Memory: Record Pattern",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2040, 160],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": MEMORY_RECORD_JS}
    },
    # After ReAct: DB Save Email
    {
        "id": "n_mem_react",
        "name": "Memory: Record ReAct Pattern",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3600, 460],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": MEMORY_RECORD_REACT_JS}
    }
]

# Patch connections:
# IF: Needs Scrape [YES] currently goes to Wait 1.5s
# → change to Memory: Check Domain Cache → Wait 1.5s
conns = wf["connections"]

# Find IF: Needs Scrape YES connection
if_scrape = conns.get("IF: Needs Scrape", {})
# YES branch currently → Wait 1.5s (index 0)
if_scrape["main"][0] = [{"node": "Memory: Check Domain Cache", "type": "main", "index": 0}]

conns["Memory: Check Domain Cache"] = {
    "main": [[{"node": "Wait 1.5s", "type": "main", "index": 0}]]
}

# After DB: Save Email → Memory: Record Pattern
# Currently DB: Save Email has no outgoing connections - add one
conns["DB: Save Email"] = {
    "main": [[{"node": "Memory: Record Pattern", "type": "main", "index": 0}]]
}

# After ReAct: DB Save Email → Memory: Record ReAct Pattern
conns["ReAct: DB Save Email"] = {
    "main": [[{"node": "Memory: Record ReAct Pattern", "type": "main", "index": 0}]]
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
        mem_nodes = [n["name"] for n in result["nodes"] if "Memory:" in n["name"]]
        print(f"SUCCESS! Total nodes: {len(result['nodes'])}")
        print(f"Memory nodes: {mem_nodes}")
        # Verify key connections
        if_s = result["connections"].get("IF: Needs Scrape", {}).get("main", [])
        print(f"IF: Needs Scrape YES -> {if_s[0][0]['node'] if if_s and if_s[0] else '?'}")
        db_s = result["connections"].get("DB: Save Email", {}).get("main", [])
        print(f"DB: Save Email -> {db_s[0][0]['node'] if db_s and db_s[0] else 'none'}")
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)
