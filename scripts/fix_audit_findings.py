"""
Fix audit findings (classes B, C, F, G) from audit_all_workflows.py:
  B: Flow 13 Wait unit milliseconds -> 2 seconds
  C: interval schedule triggers -> cronExpression (drift/zombie protection)
  F: Flow 3 reference to renamed node Parse DeepSeek Response
  G: Flow 1 dead credential -> Tvuhat51UDCzKwnE (only if node enabled)
Reactivates every touched workflow. Run on VPS: N8N_API_KEY + N8N_BASE env.
"""
import json, os, ssl, urllib.request

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
WHITELIST = {"executionOrder","errorWorkflow","saveManualExecutions","callerPolicy","timezone",
             "saveExecutionProgress","saveDataSuccessExecution","saveDataErrorExecution","executionTimeout"}

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, context=CTX) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {path}: {e.read().decode()[:300]}") from None

def put(wf):
    settings = {k: v for k, v in (wf.get("settings") or {}).items() if k in WHITELIST}
    req("PUT", f"/api/v1/workflows/{wf['id']}",
        {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": settings})

def cycle(wid):
    req("POST", f"/api/v1/workflows/{wid}/deactivate")
    return req("POST", f"/api/v1/workflows/{wid}/activate").get("active")

def to_cron(iv):
    if "minutesInterval" in iv:
        return f"*/{iv['minutesInterval']} * * * *"
    h = iv.get("triggerAtHour", 0); m = iv.get("triggerAtMinute", 0)
    return f"{m} {h} * * *"

# --- C: interval triggers -> cron (all flagged flows) ---
CRON_FLOWS = ["c04bfd2b-2c28-4118-8075-6367c612fd7c", "crCYiC5LUCvCyeIQ",
              "qH2OuOEfJBVWHj3A", "tv434oBgRQrUhqAe", "C2D45wHhF6sMzTVe",
              "8rTfJPgE7THZfatr", "VBfS8H71yz0ArkWT", "47sePMK8lKZGxpvo"]
for wid in CRON_FLOWS:
    try:
        wf = req("GET", f"/api/v1/workflows/{wid}")
        touched = False
        for n in wf["nodes"]:
            if n["type"] == "n8n-nodes-base.scheduleTrigger" and not n.get("disabled"):
                ivs = n["parameters"].get("rule", {}).get("interval", [])
                new = []
                for iv in ivs:
                    if iv.get("field") == "cronExpression":
                        new.append(iv)
                    else:
                        cron = to_cron(iv)
                        new.append({"field": "cronExpression", "expression": cron})
                        print(f"{wf['name'][:36]} :: {n['name']}: {json.dumps(iv)[:50]} -> cron '{cron}'")
                        touched = True
                n["parameters"]["rule"]["interval"] = new
            # --- B: Wait milliseconds fix (Flow 13 sits in this list) ---
            if n["type"] == "n8n-nodes-base.wait" and n["parameters"].get("unit") == "milliseconds":
                n["parameters"]["amount"] = 2
                n["parameters"]["unit"] = "seconds"
                print(f"{wf['name'][:36]} :: {n['name']}: milliseconds -> 2 seconds")
                touched = True
        if touched:
            put(wf)
            print(f"  -> saved, active={cycle(wid)}")
    except RuntimeError as e:
        print(f"FAILED {wid}: {e}")

# --- F: Flow 3 missing node reference ---
wf = req("GET", "/api/v1/workflows/Qq5t3rtSpWVNxH9g")
names = {n["name"] for n in wf["nodes"]}
target = "Parse LLM Response" if "Parse LLM Response" in names else None
if target:
    for n in wf["nodes"]:
        blob = json.dumps(n["parameters"], ensure_ascii=False)
        if "$('Parse DeepSeek Response')" in blob:
            n["parameters"] = json.loads(
                blob.replace("$('Parse DeepSeek Response')", f"$('{target}')"))
            print(f"Flow 3 :: {n['name']}: Parse DeepSeek Response -> {target}")
    put(wf)
    print(f"  -> saved, active={cycle('Qq5t3rtSpWVNxH9g')}")
else:
    print("Flow 3: no 'Parse LLM Response' node found — manual review needed. Nodes:", sorted(names))

# --- G: Flow 1 dead credential ---
wf = req("GET", "/api/v1/workflows/JRXuonKppWpNM3UB")
touched = False
for n in wf["nodes"]:
    creds = n.get("credentials") or {}
    for k, v in creds.items():
        if isinstance(v, dict) and v.get("id") == "ZjjVGIqiRAUVlCk6":
            print(f"Flow 1 :: {n['name']}: disabled={n.get('disabled', False)} dead cred", end="")
            if n.get("disabled"):
                print(" -> node disabled, skipping")
            else:
                creds[k] = {"id": "Tvuhat51UDCzKwnE", "name": "Postgres account"}
                touched = True
                print(" -> swapped to Tvuhat51UDCzKwnE")
if touched:
    put(wf)
    print(f"  -> saved, active={cycle('JRXuonKppWpNM3UB')}")
