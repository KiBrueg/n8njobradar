"""
Add Corrective RAG to Flow 4 (Job APIs).
After IF: is_job_related → NO:
  CRAG: Jina Fetch → CRAG: LLM Retry → CRAG: Parse Retry → CRAG: DB Write Retry
Source URL comes from Normalize: API Job → normalized_input.raw_meta.url
"""
import json, os, urllib.request, ssl, sys

API_KEY = os.environ["N8N_API_KEY"]
BASE = os.environ["N8N_BASE"]
FLOW_ID = "HDJIQgfBv2Coa4jo"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

wf = req("GET", f"/api/v1/workflows/{FLOW_ID}")
print(f"Fetched Flow 4: {len(wf['nodes'])} nodes")

CRAG_PARSE_JS = r"""const body = $input.item.json;
const origNI = $('Normalize: API Job').item.json.normalized_input;
let jobEvent;
try {
  const choice = ((body.choices || [])[0] || {});
  let raw = (choice.message && choice.message.content) ? choice.message.content : '';
  raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  raw = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
  jobEvent = JSON.parse(raw);
} catch(e) { return []; }
if (!jobEvent || !jobEvent.is_job_related || jobEvent.action === 'ignore') return [];
const esc = v => v == null ? 'NULL' : "'" + String(v).replace(/'/g, "''") + "'";
const en  = (v, t) => v ? "'" + String(v).replace(/'/g,"''") + "'::" + t : 'NULL';
const arr = vals => {
  if (!vals || !vals.length) return "'{}'";
  const p = vals.map(v => '"' + String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"') + '"');
  return "'" + '{' + p.join(',') + '}' + "'";
};
if (jobEvent.company_id) {
  jobEvent.company_id = jobEvent.company_id.toLowerCase()
    .replace(/[^a-z0-9-]/g,'-').replace(/--+/g,'-').replace(/^-|-$/g,'');
}
const sourceUrl = (origNI.raw_meta && origNI.raw_meta.url) || jobEvent.source_url || null;
const fuzzy = jobEvent.job_id_fuzzy || [
  jobEvent.company_id || 'unknown',
  (jobEvent.job_title||'unknown').toLowerCase().replace(/[^a-z0-9]/g,'-').substring(0,40),
  (sourceUrl||'x').replace(/https?:\/\//,'').replace(/[^a-z0-9]/g,'-').substring(0,50)
].join('__');
const wmRaw = jobEvent.work_mode ? String(jobEvent.work_mode).toLowerCase().replace(/[-\s]/g,'_') : null;
const wmMap = {on_site:'onsite',onsite:'onsite',remote:'remote',full_remote:'remote',fully_remote:'remote',hybrid:'hybrid'};
return [{ json: {
  company_id_sql:   esc(jobEvent.company_id || 'unknown'),
  company_name_sql: esc(jobEvent.company_name || 'Unknown'),
  job_id_fuzzy_sql: esc(fuzzy),
  job_title_sql:    esc(jobEvent.job_title || ''),
  location_sql:     esc(jobEvent.location || null),
  source_url_sql:   esc(sourceUrl),
  summary_sql:      esc((jobEvent.summary || '') + ' [crag-retry]'),
  work_mode_sql:    en(wmMap[wmRaw] || null, 'work_mode_enum'),
  tech_stack_sql:   arr(Array.isArray(jobEvent.tech_stack) ? jobEvent.tech_stack : []),
  stage_sql:        en('discovered', 'job_stage_enum'),
} }];"""

CRAG_SQL = """WITH co AS (
  INSERT INTO companies (company_id, name, meta)
  VALUES ({{ $json.company_id_sql }}, {{ $json.company_name_sql }}, '{}')
  ON CONFLICT (tenant_id, company_id) DO UPDATE SET updated_at = NOW()
)
INSERT INTO jobs (
  job_id_fuzzy, company_id, job_title, location,
  source_url, source_input, current_stage, summary, work_mode, tech_stack
) VALUES (
  {{ $json.job_id_fuzzy_sql }},
  {{ $json.company_id_sql }},
  {{ $json.job_title_sql }},
  {{ $json.location_sql }},
  {{ $json.source_url_sql }},
  'scraped'::input_source_enum,
  {{ $json.stage_sql }},
  {{ $json.summary_sql }},
  {{ $json.work_mode_sql }},
  {{ $json.tech_stack_sql }}
)
ON CONFLICT (tenant_id, job_id_fuzzy) DO NOTHING;"""

LLM_BODY = ("={{ JSON.stringify({ model: 'qwen/qwen3-30b-a3b-instruct-2507', max_tokens: 2048,"
            " messages: [{ role: 'system', content: $env.JOBRADAR_SYSTEM_PROMPT },"
            " { role: 'user', content: JSON.stringify({ ...($('Normalize: API Job').item.json.normalized_input),"
            " raw_text: ($('Normalize: API Job').item.json.normalized_input.raw_text || '') +"
            " '\\n\\n--- FULL JOB PAGE (Jina CRAG) ---\\n' + String($input.item.json).substring(0, 5000) }) }] }) }}")

new_nodes = [
    {
        "id": "n_f4_crag_jina",
        "name": "CRAG: Jina Fetch",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2632, 560],
        "onError": "continueErrorOutput",
        "parameters": {
            "url": "=https://r.jina.ai/{{ $('Normalize: API Job').item.json.normalized_input.raw_meta.url }}",
            "options": {"timeout": 10000}
        }
    },
    {
        "id": "n_f4_crag_llm",
        "name": "CRAG: LLM Retry",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2856, 560],
        "onError": "continueErrorOutput",
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"},
                {"name": "content-type", "value": "application/json"}
            ]},
            "sendBody": True,
            "contentType": "raw",
            "rawContentType": "application/json",
            "body": LLM_BODY,
            "options": {"timeout": 60000}
        }
    },
    {
        "id": "n_f4_crag_parse",
        "name": "CRAG: Parse Retry",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [3080, 560],
        "parameters": {"mode": "runOnceForEachItem", "jsCode": CRAG_PARSE_JS}
    },
    {
        "id": "n_f4_crag_db",
        "name": "CRAG: DB Write Retry",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [3304, 560],
        "onError": "continueErrorOutput",
        "parameters": {
            "operation": "executeQuery",
            "query": CRAG_SQL,
            "options": {}
        },
        "credentials": {
            "postgres": {"id": "Tvuhat51UDCzKwnE", "name": "Postgres account"}
        }
    }
]

conns = wf["connections"]

# Patch IF: is_job_related NO branch → CRAG: Jina Fetch
if_conn = conns.get("IF: is_job_related", {})
if_main = if_conn.get("main", [[], []])
if len(if_main) < 2:
    if_main.append([])
if_main[1] = [{"node": "CRAG: Jina Fetch", "type": "main", "index": 0}]

conns["CRAG: Jina Fetch"] = {
    "main": [
        [{"node": "CRAG: LLM Retry", "type": "main", "index": 0}],
        []
    ]
}
conns["CRAG: LLM Retry"] = {
    "main": [[{"node": "CRAG: Parse Retry", "type": "main", "index": 0}]]
}
conns["CRAG: Parse Retry"] = {
    "main": [[{"node": "CRAG: DB Write Retry", "type": "main", "index": 0}]]
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
        crag = [n["name"] for n in result["nodes"] if n["name"].startswith("CRAG:")]
        print(f"SUCCESS! Total nodes: {len(result['nodes'])}")
        print(f"CRAG nodes: {crag}")
        if_no = result["connections"].get("IF: is_job_related", {}).get("main", [])
        print(f"IF NO branch -> {if_no[1] if len(if_no) > 1 else 'EMPTY'}")
except urllib.error.HTTPError as e:
    print("Error:", e.code, e.read().decode(), file=sys.stderr); sys.exit(1)
