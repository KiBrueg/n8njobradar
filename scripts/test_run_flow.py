"""
E2E test-run a schedule-only workflow: temporarily set its cron to fire in
+2 min (Europe/Berlin), wait for the execution, report status + failing node,
then restore the original cron. Usage: python3 test_run_flow.py <workflow_id> [max_wait_s]
Env: N8N_API_KEY, N8N_BASE.
"""
import json, os, ssl, sys, time, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
WID     = sys.argv[1]
MAX_WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 360
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
    if settings.get("callerPolicy") not in ("any","none","workflowsFromAList","workflowsFromSameOwner"):
        settings.pop("callerPolicy", None)
    req("PUT", f"/api/v1/workflows/{wf['id']}",
        {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": settings})

def cycle():
    req("POST", f"/api/v1/workflows/{WID}/deactivate")
    req("POST", f"/api/v1/workflows/{WID}/activate")

def set_cron(expr):
    wf = req("GET", f"/api/v1/workflows/{WID}")
    saved = None
    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.scheduleTrigger" and not n.get("disabled"):
            saved = n["parameters"]["rule"]["interval"]
            n["parameters"]["rule"]["interval"] = [{"field": "cronExpression", "expression": expr}]
            break
    put(wf); cycle()
    return saved

def restore_cron(saved):
    wf = req("GET", f"/api/v1/workflows/{WID}")
    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.scheduleTrigger" and not n.get("disabled"):
            n["parameters"]["rule"]["interval"] = saved
            break
    put(wf); cycle()

last = req("GET", f"/api/v1/executions?workflowId={WID}&limit=1")["data"]
last_id = int(last[0]["id"]) if last else 0

fire = datetime.now(ZoneInfo("Europe/Berlin")) + timedelta(minutes=2)
expr = f"{fire.minute} {fire.hour} * * *"
saved = set_cron(expr)
if saved is None:
    print("NO SCHEDULE TRIGGER FOUND"); sys.exit(1)
print(f"cron set to '{expr}' (fires ~{fire.strftime('%H:%M')} Berlin), waiting...")

deadline = time.time() + 150 + MAX_WAIT
result = None
try:
    while time.time() < deadline:
        time.sleep(15)
        ex = req("GET", f"/api/v1/executions?workflowId={WID}&limit=1")["data"]
        if ex and int(ex[0]["id"]) > last_id:
            e = ex[0]
            if e["status"] in ("success", "error", "crashed"):
                result = e
                break
            print(f"  running... (exec {e['id']})")
finally:
    restore_cron(saved)
    print("original cron restored")

if not result:
    print("TIMEOUT: no finished execution observed")
    sys.exit(2)

print(f"RESULT: {result['status'].upper()} exec {result['id']} "
      f"({result['startedAt'][11:19]} -> {str(result.get('stoppedAt'))[11:19]})")
if result["status"] != "success":
    detail = req("GET", f"/api/v1/executions/{result['id']}?includeData=true")
    rd = detail["data"]["resultData"]
    err = rd.get("error", {})
    print("lastNodeExecuted:", rd.get("lastNodeExecuted"))
    print("error:", str(err.get("message"))[:300])
    node = err.get("node", {}).get("name")
    if node: print("node:", node)
    sys.exit(3)
