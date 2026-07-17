"""
Static audit of ALL n8n workflows: walks every node of every workflow and
flags known bug classes. Read-only. Run on VPS: N8N_API_KEY + N8N_BASE env.

Checks:
  A1 Code each-item: `return [` / $input.all() / .map( producing items
  A2 Code all-items: $('X').item.json (needs itemMatching(i))
  A3 Code: process.env (unavailable in task runner)
  B  Wait: invalid unit
  C  Schedule: interval-based (not cron) -> drift/zombie risk
  D  Postgres: unknown job_stage_enum literals
  E  HTTP: scrapegraphai without onError; SerpAPI location=Deutschland
  F  $('Name') references to nodes absent from the workflow
  G  Credentials pointing to deleted ZjjVGIqiRAUVlCk6
"""
import json, os, re, ssl, urllib.request

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

JOB_STAGES = {"discovered","applied","screening","interview","test_task","offer",
              "rejected","withdrawn","on_hold","application_failed"}
DEAD_CREDS = {"ZjjVGIqiRAUVlCk6"}

def req(path):
    r = urllib.request.Request(BASE + path, headers={"X-N8N-API-KEY": API_KEY})
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wfs = req("/api/v1/workflows?limit=100")["data"]
total_nodes = 0
findings = []

for wf in wfs:
    names = {n["name"] for n in wf["nodes"]}
    act = "ACTIVE" if wf["active"] else "off"
    for n in wf["nodes"]:
        total_nodes += 1
        t = n["type"].split(".")[-1]
        p = n.get("parameters", {})
        blob = json.dumps(p, ensure_ascii=False)
        loc = f"{wf['name'][:38]} [{act}] :: {n['name']}"

        if t == "code":
            code = p.get("jsCode", "")
            mode = p.get("mode", "runOnceForAllItems")
            if n.get("disabled"): continue
            if mode == "runOnceForEachItem":
                if re.search(r"return\s*\[", code):
                    findings.append(("A1", loc, "each-item returns array"))
                if "$input.all()" in code:
                    findings.append(("A1", loc, "each-item uses $input.all()"))
            else:
                for m in set(re.findall(r"\$\('([^']+)'\)\.item\.json", code)):
                    findings.append(("A2", loc, f"all-items uses $('{m}').item (needs itemMatching)"))
            if "process.env" in code:
                findings.append(("A3", loc, "process.env in Code node"))

        if t == "wait":
            if p.get("unit") not in (None, "seconds", "minutes", "hours", "days"):
                findings.append(("B", loc, f"invalid wait unit: {p.get('unit')}"))

        if t == "scheduleTrigger" and wf["active"] and not n.get("disabled"):
            for iv in p.get("rule", {}).get("interval", [{}]):
                if iv.get("field") not in ("cronExpression", None) or (iv.get("field") is None and "expression" not in iv):
                    if iv.get("field") != "cronExpression":
                        findings.append(("C", loc, f"interval trigger (not cron): {json.dumps(iv)[:60]}"))

        if t == "postgres":
            q = p.get("query", "")
            for m in re.findall(r"current_stage\s*(?:=|!=|NOT IN|IN)\s*\(?([^)\n]+)\)?", q, re.I):
                for lit in re.findall(r"'([a-z_]+)'", m):
                    if lit not in JOB_STAGES:
                        findings.append(("D", loc, f"unknown job_stage: '{lit}'"))

        if t == "httpRequest":
            url = str(p.get("url", ""))
            if "scrapegraphai" in url and n.get("onError") != "continueErrorOutput" and not n.get("disabled"):
                findings.append(("E", loc, "SGai call without onError (dead API)"))
            if "serpapi" in url and '"location", "value": "Deutschland"' in blob.replace("'", '"'):
                findings.append(("E", loc, "SerpAPI location=Deutschland"))
            for prm in p.get("queryParameters", {}).get("parameters", []):
                if prm.get("name") == "location" and prm.get("value") == "Deutschland":
                    findings.append(("E", loc, "SerpAPI location=Deutschland"))

        for m in set(re.findall(r"\$\('([^']+)'\)", blob)):
            if m not in names:
                findings.append(("F", loc, f"reference to missing node $('{m}')"))

        for cred in (n.get("credentials") or {}).values():
            if isinstance(cred, dict) and cred.get("id") in DEAD_CREDS:
                findings.append(("G", loc, f"dead credential {cred.get('id')}"))

print(f"Scanned {len(wfs)} workflows, {total_nodes} nodes. Findings: {len(findings)}\n")
for cls, loc, msg in sorted(findings):
    print(f"[{cls}] {loc} -> {msg}")
