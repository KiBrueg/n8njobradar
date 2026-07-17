"""
Fix per-item Code nodes that return arrays / use `return []` (invalid in
runOnceForEachItem) across Flows 4, 7, 13, 14. Converts multi-item producers
to runOnceForAllItems loops with itemMatching; strips array wrappers on
single-item transforms. Also fixes SerpAPI location Deutschland->Germany.
Run on VPS: N8N_API_KEY + N8N_BASE from env.
"""
import json, os, ssl, sys, urllib.request

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
SETTINGS_WHITELIST = {"executionOrder","errorWorkflow","saveManualExecutions","callerPolicy",
                      "timezone","saveExecutionProgress","saveDataSuccessExecution",
                      "saveDataErrorExecution","executionTimeout"}

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.loads(resp.read())

def put_workflow(wf):
    settings = {k: v for k, v in (wf.get("settings") or {}).items() if k in SETTINGS_WHITELIST}
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": settings}
    return req("PUT", f"/api/v1/workflows/{wf['id']}", body)

def node(wf, name):
    return next(n for n in wf["nodes"] if n["name"] == name)

def fix_crag(code, upstream):
    """Per-item parse -> all-items loop; return[] -> continue."""
    assert f"$('{upstream}').item.json.normalized_input" in code, "upstream ref not found"
    code = code.replace("const body = $input.item.json;\n", "")
    code = code.replace(f"const origNI = $('{upstream}').item.json.normalized_input;\n", "")
    code = code.replace("return [];", "continue;")
    code = code.replace("return [{ json: {", "out.push({ json: {")
    code = code.rstrip()
    assert code.endswith("} }];"), f"unexpected tail: {code[-30:]!r}"
    code = code[: -len("} }];")] + "} });"
    header = ("const out = [];\nconst items = $input.all();\n"
              "for (let i = 0; i < items.length; i++) {\n"
              "const body = items[i].json;\n"
              f"const origNI = $('{upstream}').itemMatching(i).json.normalized_input;\n")
    return header + code + "\n}\nreturn out;"

BACKUP_PARSE_JS = """const out = [];
for (const it of $input.all()) {
  const item = it.json;
  const scraperResult = item.result || item;
  const jobs = Array.isArray(scraperResult.result) ? scraperResult.result :
               Array.isArray(scraperResult) ? scraperResult : [];
  for (const j of jobs) out.push({ json: {
    title: j.title || j.job_title || '',
    url: j.url || j.application_url || item.url || '',
    location: j.location || '',
    work_mode: j.work_mode || j.remote || '',
    tech_stack: Array.isArray(j.tech_stack) ? j.tech_stack : [],
    summary: j.summary || j.description || '',
    _source: 'backup_scraper'
  }});
}
return out;"""

EXTRACT_COMPANIES_JS = r"""const out = [];
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const query = $('Build Search Queries').itemMatching(i).json;
  const raw = items[i].json;
  const text = typeof raw === 'string' ? raw : (raw.body || raw.data || JSON.stringify(raw));

  const EMAIL_RE = /[\w.+\-]+@[\w\-]+\.[\w.\-]{2,}/g;
  const BAD_RE = /noreply|no[-_]reply|donotreply|newsletter|info@|hallo@|kontakt@|service@|support@|post@|office@|sbv|gelbeseiten|yelp/i;
  const emails = (text.match(EMAIL_RE) || []).filter(e => !BAD_RE.test(e) && e.length > 6);

  const companies = [];
  const blocks = text.split(/\n(?=##\s)/);
  for (const block of blocks) {
    const nameMatch = block.match(/^##\s+(.+)/);
    if (!nameMatch) continue;
    const name = nameMatch[1].trim();
    if (name.length < 3 || name.length > 80) continue;
    const websiteMatch = block.match(/(?:Website|Webseite|www)[:\s]+([\w\-.]+\.[a-z]{2,})(?:\s|$)/i)
      || block.match(/https?:\/\/([\w\-.]+\.[a-z]{2,})/i);
    const website = websiteMatch ? websiteMatch[1].replace(/^https?:\/\//, '').replace(/\/.*$/, '') : null;
    const blockEmails = (block.match(EMAIL_RE) || []).filter(e => !BAD_RE.test(e));
    companies.push({ name, website, email: blockEmails[0] || null });
  }
  if (companies.length === 0 && emails.length > 0) {
    for (const email of emails.slice(0, 10)) {
      companies.push({ name: email.split('@')[1].split('.')[0], website: null, email });
    }
  }
  for (const co of companies.slice(0, 20)) out.push({ json: {
    company_name: co.name,
    website: co.website,
    contact_email: co.email,
    category: query.category,
    pitch: query.pitch,
    city: query.city,
    source_url: query.url,
    input_source: 'prospecting'
  }});
}
return out;"""

changed = []

# --- Flow 7: CRAG Parse Retry + Backup Parse Jobs -> all-items ---
wf = req("GET", "/api/v1/workflows/VBfS8H71yz0ArkWT")
n = node(wf, "CRAG: Parse Retry")
n["parameters"]["jsCode"] = fix_crag(n["parameters"]["jsCode"], "Normalize Item")
n["parameters"]["mode"] = "runOnceForAllItems"
n = node(wf, "Backup: Parse Jobs")
n["parameters"]["jsCode"] = BACKUP_PARSE_JS
n["parameters"]["mode"] = "runOnceForAllItems"
put_workflow(wf); changed.append(("VBfS8H71yz0ArkWT", "Flow7: CRAG+Backup -> allItems"))

# --- Flow 4: CRAG Parse Retry -> all-items; SerpAPI location fix ---
wf = req("GET", "/api/v1/workflows/HDJIQgfBv2Coa4jo")
n = node(wf, "CRAG: Parse Retry")
n["parameters"]["jsCode"] = fix_crag(n["parameters"]["jsCode"], "Normalize: API Job")
n["parameters"]["mode"] = "runOnceForAllItems"
n = node(wf, "SerpAPI: Fetch Google Jobs")
for p in n["parameters"]["queryParameters"]["parameters"]:
    if p["name"] == "location" and p["value"] == "Deutschland":
        p["value"] = "Germany"
put_workflow(wf); changed.append(("HDJIQgfBv2Coa4jo", "Flow4: CRAG -> allItems; location=Germany"))

# --- Flow 13: strip array wrappers (stay per-item) ---
wf = req("GET", "/api/v1/workflows/C2D45wHhF6sMzTVe")
for name in ["ReAct: Extract Contact", "ReAct: Extract Impressum",
             "Memory: Check Domain Cache", "Memory: Record Pattern", "Memory: Record ReAct Pattern"]:
    n = node(wf, name)
    code = n["parameters"]["jsCode"]
    assert code.count("return [{ json:") == 1, f"{name}: unexpected return count"
    code = code.replace("return [{ json: item }];", "return { json: item };")
    if "return [{ json: {" in code:
        code = code.replace("return [{ json: {", "return { json: {")
        tail = code.rstrip()
        assert tail.endswith("} }];"), f"{name}: unexpected tail {tail[-30:]!r}"
        code = tail[: -len("} }];")] + "} };"
    n["parameters"]["jsCode"] = code
put_workflow(wf); changed.append(("C2D45wHhF6sMzTVe", "Flow13: 5 nodes array->object"))

# --- Flow 14: Extract Companies -> all-items ---
wf = req("GET", "/api/v1/workflows/8rTfJPgE7THZfatr")
n = node(wf, "Extract Companies")
n["parameters"]["jsCode"] = EXTRACT_COMPANIES_JS
n["parameters"]["mode"] = "runOnceForAllItems"
put_workflow(wf); changed.append(("8rTfJPgE7THZfatr", "Flow14: Extract Companies -> allItems"))

# --- Re-register triggers (API update deregisters schedule triggers) ---
for wid, desc in changed:
    req("POST", f"/api/v1/workflows/{wid}/deactivate")
    r = req("POST", f"/api/v1/workflows/{wid}/activate")
    print(f"OK {desc} | active={r.get('active')}")
