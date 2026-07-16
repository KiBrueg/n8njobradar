"""
Push updated spec/prompt-system.txt into the LLM Call nodes of Flow 7 and Flow 4.
Reads API key from N8N_API_KEY env var.
"""
import json, os, ssl, sys, urllib.request
from pathlib import Path

API_KEY  = os.environ["N8N_API_KEY"]
BASE     = os.environ["N8N_BASE"]
FLOWS    = {
    "Flow 7 (Gewerbe)":   "VBfS8H71yz0ArkWT",
    "Flow 4 (Job APIs)":  "HDJIQgfBv2Coa4jo",
}
LLM_NODE_NAMES = {"LLM Call (OpenRouter)", "LLM Call", "OpenRouter: Parse Job"}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE

PROMPT_PATH = Path(__file__).parent.parent / "spec" / "prompt-system.txt"
NEW_PROMPT  = PROMPT_PATH.read_text(encoding="utf-8")
print(f"Prompt loaded: {len(NEW_PROMPT)} chars from {PROMPT_PATH.name}")

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

for flow_name, flow_id in FLOWS.items():
    print(f"\n{flow_name} ({flow_id})")
    wf = api("GET", f"/api/v1/workflows/{flow_id}")
    updated = False
    for n in wf["nodes"]:
        if n["name"] not in LLM_NODE_NAMES:
            continue
        params = n.get("parameters", {})
        # n8n HTTP Request node with OpenRouter: system prompt is in messages array
        msgs = params.get("body", {}).get("messages") or params.get("messages") or []
        if isinstance(msgs, list):
            for msg in msgs:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = NEW_PROMPT
                    updated = True
                    print(f"  Updated messages[system] in {n['name']}")
        # also check jsonBody string
        if "jsonBody" in params:
            try:
                body_obj = json.loads(params["jsonBody"])
                for msg in body_obj.get("messages", []):
                    if msg.get("role") == "system":
                        msg["content"] = NEW_PROMPT
                        updated = True
                params["jsonBody"] = json.dumps(body_obj)
                print(f"  Updated jsonBody[system] in {n['name']}")
            except Exception:
                pass
        # check direct systemMessage field
        for key in ("systemMessage", "system_message", "system"):
            if key in params:
                params[key] = NEW_PROMPT
                updated = True
                print(f"  Updated params[{key}] in {n['name']}")

    if not updated:
        # dump node names so we can identify correct one
        llm_nodes = [n["name"] for n in wf["nodes"]
                     if any(k in n["name"].lower() for k in ("llm","openrouter","claude","gpt","qwen"))]
        print(f"  No LLM node matched. Candidates: {llm_nodes}")
        continue

    try:
        api("PUT", f"/api/v1/workflows/{flow_id}", {
            "name": wf["name"], "nodes": wf["nodes"],
            "connections": wf["connections"], "settings": wf.get("settings", {})
        })
        print(f"  Saved.")
    except urllib.error.HTTPError as e:
        print(f"  Save error: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
