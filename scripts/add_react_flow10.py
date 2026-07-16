"""
Add ReAct (Reasoning + Acting) sub-page email enrichment to Flow 10.
After IF: Email Found → NO, instead of immediate Log Not Found:
  Try /contact → extract → if found: save
                         → if not:  Try /impressum → extract → if found: save
                                                              → if not:  Log Not Found
"""
import json, os, urllib.request, ssl, sys

API_KEY = os.environ["N8N_API_KEY"]
BASE = os.environ["N8N_BASE"]
FLOW_ID = "C2D45wHhF6sMzTVe"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers={
        "X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"
    }, method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wf = req("GET", f"/api/v1/workflows/{FLOW_ID}")
print(f"Fetched Flow 10: {len(wf['nodes'])} nodes")

# --- Extract email helper (shared logic) ---
EXTRACT_JS = """const classified = $('Classify + Raw Text Check').item.json;
const body = $input.item.json;
const text = typeof body === 'string' ? body : (body.body || body.data || JSON.stringify(body));
const EMAIL_RE = /[\\w.+\\-]+@[\\w\\-]+\\.[\\w.\\-]{2,}/g;
const BAD_RE = /noreply|no[-_]reply|donotreply|mailer|bounce|unsubscribe|newsletter|sbv|betriebsrat|datenschutz|widerruf/i;
const PREF_RE = /hr@|bewerbung@|karriere@|jobs@|personal@|recruiting@|talent@|apply@/i;
const emails = (text.match(EMAIL_RE) || []).filter(e => !BAD_RE.test(e) && e.includes('@') && e.length > 5);
const email = emails.find(e => PREF_RE.test(e)) || emails[0] || null;
return [{ json: { ...classified, found_email: email, react_page: REACT_PAGE } }];"""

CONTACT_EXTRACT = EXTRACT_JS.replace("REACT_PAGE", "'contact'")
IMPRESSUM_EXTRACT = EXTRACT_JS.replace("REACT_PAGE", "'impressum'")

# Base domain extraction from scrape_url (strips path, keeps origin)
DOMAIN_EXPR = "{{ ($json.scrape_url || '').replace(/^(https?:\\/\\/[^\\/]+).*/, '$1') }}"
DOMAIN_EXPR_CLS = "{{ ($('Classify + Raw Text Check').item.json.scrape_url || '').replace(/^(https?:\\/\\/[^\\/]+).*/, '$1') }}"

DB_SAVE_SQL = """UPDATE jobs
SET contact_email = '{{ $json.found_email.replace(/'/g, "''") }}',
    updated_at = NOW()
WHERE company_id = '{{ $json.company_id }}'
  AND contact_email IS NULL;"""

# --- 7 new ReAct nodes ---
new_nodes = [
    # 1: Try /contact page via Jina
    {
        "id": "n_react_jina_c",
        "name": "ReAct: Jina /contact",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2044, 460],
        "onError": "continueErrorOutput",
        "parameters": {
            "url": f"=https://r.jina.ai/{DOMAIN_EXPR}/contact",
            "options": {"timeout": 8000}
        }
    },
    # 2: Extract email from /contact
    {
        "id": "n_react_ext_c",
        "name": "ReAct: Extract Contact",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2268, 460],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": CONTACT_EXTRACT}
    },
    # 3: IF email found on /contact?
    {
        "id": "n_react_if1",
        "name": "IF: ReAct #1?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [2492, 460],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{
                    "id": "react1_cond",
                    "leftValue": "={{ $json.found_email }}",
                    "rightValue": "",
                    "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}
                }],
                "combinator": "and"
            },
            "options": {}
        }
    },
    # 4: Try /impressum page via Jina (if /contact failed)
    {
        "id": "n_react_jina_i",
        "name": "ReAct: Jina /impressum",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2716, 540],
        "onError": "continueErrorOutput",
        "parameters": {
            "url": f"=https://r.jina.ai/{DOMAIN_EXPR_CLS}/impressum",
            "options": {"timeout": 8000}
        }
    },
    # 5: Extract email from /impressum
    {
        "id": "n_react_ext_i",
        "name": "ReAct: Extract Impressum",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [2940, 540],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": IMPRESSUM_EXTRACT}
    },
    # 6: IF email found on /impressum?
    {
        "id": "n_react_if2",
        "name": "IF: ReAct #2?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [3164, 540],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{
                    "id": "react2_cond",
                    "leftValue": "={{ $json.found_email }}",
                    "rightValue": "",
                    "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}
                }],
                "combinator": "and"
            },
            "options": {}
        }
    },
    # 7: Save email to DB (shared endpoint for both YES branches)
    {
        "id": "n_react_db",
        "name": "ReAct: DB Save Email",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [3388, 460],
        "onError": "continueErrorOutput",
        "parameters": {
            "operation": "executeQuery",
            "query": DB_SAVE_SQL,
            "options": {}
        },
        "credentials": {
            "postgres": {"id": "Tvuhat51UDCzKwnE", "name": "Postgres account"}
        }
    }
]

# --- Patch connections ---
conns = wf["connections"]

# Redirect IF: Email Found NO branch from Log Not Found → ReAct: Jina /contact
if_found = conns.get("IF: Email Found", {})
if_found["main"][1] = [{"node": "ReAct: Jina /contact", "type": "main", "index": 0}]

# ReAct chain connections
conns["ReAct: Jina /contact"] = {
    "main": [[{"node": "ReAct: Extract Contact", "type": "main", "index": 0}], []]
}
conns["ReAct: Extract Contact"] = {
    "main": [[{"node": "IF: ReAct #1?", "type": "main", "index": 0}]]
}
conns["IF: ReAct #1?"] = {
    "main": [
        [{"node": "ReAct: DB Save Email", "type": "main", "index": 0}],  # YES
        [{"node": "ReAct: Jina /impressum", "type": "main", "index": 0}]  # NO
    ]
}
conns["ReAct: Jina /impressum"] = {
    "main": [[{"node": "ReAct: Extract Impressum", "type": "main", "index": 0}], []]
}
conns["ReAct: Extract Impressum"] = {
    "main": [[{"node": "IF: ReAct #2?", "type": "main", "index": 0}]]
}
conns["IF: ReAct #2?"] = {
    "main": [
        [{"node": "ReAct: DB Save Email", "type": "main", "index": 0}],  # YES
        [{"node": "Log Not Found", "type": "main", "index": 0}]           # NO
    ]
}

# --- PUT ---
put_body = {
    "name": wf["name"],
    "nodes": wf["nodes"] + new_nodes,
    "connections": conns,
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
}
data = json.dumps(put_body).encode()
r = urllib.request.Request(
    f"{BASE}/api/v1/workflows/{FLOW_ID}",
    data=data,
    headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
    method="PUT"
)
try:
    with urllib.request.urlopen(r, context=CTX) as resp:
        result = json.loads(resp.read())
        react_nodes = [n["name"] for n in result["nodes"] if n["name"].startswith("ReAct:") or n["name"].startswith("IF: ReAct")]
        print(f"SUCCESS! Total nodes: {len(result['nodes'])}")
        print(f"ReAct nodes: {react_nodes}")
        # Verify IF: Email Found NO branch
        if_no = result["connections"].get("IF: Email Found", {}).get("main", [])
        branch1 = if_no[1] if len(if_no) > 1 else "EMPTY"
        print(f"IF: Email Found NO -> {branch1}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
