"""Fix DB: Companies Without Email query - remove j.raw_text which doesn't exist in DB."""
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

FIXED_QUERY = """SELECT DISTINCT ON (j.company_id)
  j.id as job_id,
  j.company_id,
  c.name as company_name,
  j.job_title,
  j.job_type,
  j.work_mode,
  j.source_url
FROM jobs j
LEFT JOIN companies c ON j.company_id = c.company_id
WHERE j.contact_email IS NULL
  AND j.source_url IS NOT NULL
  AND j.current_stage NOT IN ('rejected', 'ignored')
  AND j.company_id NOT ILIKE '%malt%'
  AND j.source_url NOT ILIKE '%malt.de%'
  AND j.source_url NOT ILIKE '%malt.com%'
ORDER BY j.company_id, j.work_mode DESC, j.created_at DESC
LIMIT 60;"""

for n in wf["nodes"]:
    if n["name"] == "DB: Companies Without Email":
        old = n["parameters"]["query"]
        n["parameters"]["query"] = FIXED_QUERY
        print(f"Patched: removed j.raw_text from SELECT")
        print(f"Old had raw_text: {'raw_text' in old}")
        break

put_body = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {"executionOrder": "v1", "errorWorkflow": "mdV9VERzHYVcM5vZ"}
}
data = json.dumps(put_body).encode()
r = urllib.request.Request(f"{BASE}/api/v1/workflows/{FLOW_ID}", data=data,
    headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method="PUT")
try:
    with urllib.request.urlopen(r, context=CTX) as resp:
        result = json.loads(resp.read())
        db_node = next((n for n in result["nodes"] if n["name"] == "DB: Companies Without Email"), {})
        has_raw = "raw_text" in db_node.get("parameters", {}).get("query", "")
        print(f"Updated! raw_text still in query: {has_raw}")
        print(f"Total nodes: {len(result['nodes'])}")
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)
