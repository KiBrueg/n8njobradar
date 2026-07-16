"""
Add SAP + Data Quality search queries to Flow 7 and Flow 4.

Target roles:
  - SAP Data Migration / Datenmigration (junior/Praktikum)
  - Data Quality Analyst remote
  - SAP BTP junior / demo / trainee
  - data cleaning / data annotation / data ops
  - boring remote ops roles where automation is self-applied

Flow 7 (VBfS8H71yz0ArkWT) — BA: Suchanfragen + GJobs: Suchanfragen
Flow 4 (HDJIQgfBv2Coa4jo) — SerpAPI: Queries (budget: max 250/month)
"""
import json, os, ssl, sys, urllib.request

API_KEY       = os.environ["N8N_API_KEY"]
BASE          = "https://n8n.157.180.112.46.sslip.io"
FLOW7_ID      = "VBfS8H71yz0ArkWT"
FLOW4_ID      = "HDJIQgfBv2Coa4jo"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

def patch_node_code(wf, node_name, new_code):
    for n in wf["nodes"]:
        if n["name"] == node_name:
            params = n.setdefault("parameters", {})
            if "jsCode" in params:
                params["jsCode"] = new_code
            else:
                params["code"] = new_code
            print(f"  Patched: {node_name}")
            return True
    print(f"  NOT FOUND: {node_name}", file=sys.stderr)
    return False

# ── Flow 7: BA: Suchanfragen ──────────────────────────────────────────────────
# BA API: &angebotsart=34 = Praktikum/Werkstudent, &angebotsart=1 = Vollzeit
BA_NEW_CODE = """const BASE = 'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs';
const QUERIES = [
  // existing — Automatisierung / KI
  { url: BASE + '?was=' + encodeURIComponent('KI Automatisierung') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Werkstudent Informatik') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Praktikum Digitalisierung') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Werkstudent Softwareentwicklung') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Praktikum Data Science') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Werkstudent Prozessautomatisierung') + '&angebotsart=34&size=25', label: 'ba-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('Automatisierung Python') + '&angebotsart=1&arbeitszeit=ho&size=25', label: 'ba-remote' },
  { url: BASE + '?was=' + encodeURIComponent('KI Automatisierung') + '&angebotsart=1&arbeitszeit=ho&size=25', label: 'ba-remote' },
  { url: BASE + '?was=n8n&size=25', label: 'ba-n8n' },

  // NEW — SAP entry-level
  { url: BASE + '?was=' + encodeURIComponent('SAP Praktikum') + '&angebotsart=34&size=25', label: 'ba-sap-praktikum' },
  { url: BASE + '?was=' + encodeURIComponent('SAP Werkstudent') + '&angebotsart=34&size=25', label: 'ba-sap-werkstudent' },
  { url: BASE + '?was=' + encodeURIComponent('SAP Datenmigration') + '&size=25', label: 'ba-sap-migration' },
  { url: BASE + '?was=' + encodeURIComponent('SAP BTP Praktikum') + '&size=25', label: 'ba-sap-btp' },
  { url: BASE + '?was=' + encodeURIComponent('SAP BTP Werkstudent') + '&size=25', label: 'ba-sap-btp' },
  { url: BASE + '?was=' + encodeURIComponent('SAP junior Berater') + '&size=25', label: 'ba-sap-junior' },
  { url: BASE + '?was=' + encodeURIComponent('SAP trainee') + '&size=25', label: 'ba-sap-trainee' },

  // NEW — Data Quality / Data Ops
  { url: BASE + '?was=' + encodeURIComponent('Datenqualität Analyst') + '&angebotsart=1&arbeitszeit=ho&size=25', label: 'ba-dq-remote' },
  { url: BASE + '?was=' + encodeURIComponent('Data Quality Analyst') + '&angebotsart=1&arbeitszeit=ho&size=25', label: 'ba-dq-remote' },
  { url: BASE + '?was=' + encodeURIComponent('Datenpflege') + '&angebotsart=1&arbeitszeit=ho&size=25', label: 'ba-datenpflege' },
  { url: BASE + '?was=' + encodeURIComponent('Data Annotation') + '&size=25', label: 'ba-annotation' },
];
return QUERIES.map(q => ({ json: q }));"""

# ── Flow 7: GJobs: Suchanfragen ───────────────────────────────────────────────
GJOBS_NEW_CODE = """const QUERIES = [
  // existing
  { q: 'Praktikum KI', label: 'gjobs-praktikum' },
  { q: 'Praktikum Automatisierung Python', label: 'gjobs-praktikum' },
  { q: 'Junior KI Automatisierung remote', label: 'gjobs-junior' },

  // NEW — SAP junior/entry
  { q: 'SAP BTP junior remote', label: 'gjobs-sap-btp' },
  { q: 'SAP Datenmigration junior', label: 'gjobs-sap-migration' },
  { q: 'SAP junior trainee consultant', label: 'gjobs-sap-junior' },
  { q: 'SAP data migration assistant', label: 'gjobs-sap-dma' },

  // NEW — Data Quality / Annotation
  { q: 'data quality analyst remote junior', label: 'gjobs-dq-remote' },
  { q: 'data annotation specialist remote', label: 'gjobs-annotation' },
  { q: 'data ops junior remote', label: 'gjobs-dataops' },
  { q: 'data cleaning analyst remote', label: 'gjobs-datacleaning' },
];
return QUERIES.map(q => ({ json: q }));"""

# ── Flow 4: SerpAPI: Queries (budget: 250/month, currently 4) ─────────────────
# Adding 3 → total 7 × 30 days = 210/month — safe
SERP_NEW_CODE = """// 7 queries/day × 30 days = 210 req/month (limit: 250)
// ltype=1 = Google Jobs strict remote filter
return [
  // existing
  { json: { query: 'python n8n automatisierung', ltype: '1' } },
  { json: { query: 'KI entwickler automatisierung', ltype: '1' } },
  { json: { query: 'automation engineer python', ltype: '1' } },
  { json: { query: 'python KI praktikum werkstudent', ltype: '1' } },

  // NEW — SAP + Data Quality
  { json: { query: 'SAP BTP junior consultant remote', ltype: '1' } },
  { json: { query: 'data quality analyst remote junior', ltype: '1' } },
  { json: { query: 'SAP data migration junior entry level', ltype: '1' } },
];"""

# ── apply ─────────────────────────────────────────────────────────────────────
print("Fetching Flow 7...")
wf7 = api("GET", f"/api/v1/workflows/{FLOW7_ID}")
patch_node_code(wf7, "BA: Suchanfragen", BA_NEW_CODE)
patch_node_code(wf7, "GJobs: Suchanfragen", GJOBS_NEW_CODE)

print("Updating Flow 7...")
try:
    r7 = api("PUT", f"/api/v1/workflows/{FLOW7_ID}", {
        "name": wf7["name"], "nodes": wf7["nodes"],
        "connections": wf7["connections"], "settings": wf7.get("settings", {})
    })
    print(f"  Flow 7 OK — {len(r7['nodes'])} nodes")
except urllib.error.HTTPError as e:
    print("Flow 7 error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)

print("\nFetching Flow 4...")
wf4 = api("GET", f"/api/v1/workflows/{FLOW4_ID}")
patch_node_code(wf4, "SerpAPI: Queries", SERP_NEW_CODE)

print("Updating Flow 4...")
try:
    r4 = api("PUT", f"/api/v1/workflows/{FLOW4_ID}", {
        "name": wf4["name"], "nodes": wf4["nodes"],
        "connections": wf4["connections"], "settings": wf4.get("settings", {})
    })
    print(f"  Flow 4 OK — {len(r4['nodes'])} nodes")
except urllib.error.HTTPError as e:
    print("Flow 4 error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)

print("\nDone. New queries added:")
print("  BA API  +11 (SAP Praktikum/Werkstudent/BTP/Datenmigration/trainee + DQ/Annotation)")
print("  GJobs   +8  (SAP BTP/migration/DMA + DQ/annotation/dataops)")
print("  SerpAPI +3  (SAP BTP / DQ remote / SAP migration) — total 7/day = 210/month")
