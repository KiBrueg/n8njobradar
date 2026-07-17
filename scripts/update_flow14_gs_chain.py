"""
Rework Flow 14 (Gelbe Seiten) extraction chain for reality:
GS list pages carry NO emails/websites — only `## [Name](gsbiz detail URL)`.
Chain: list (md) -> name+gsbiz URL -> detail (md) -> real website (+email if any)
-> jobs.source_url = website, contact_email if found; Flow 13 hunts email later.
Env: N8N_API_KEY, N8N_BASE.
"""
import json, os, ssl, urllib.request

API_KEY = os.environ["N8N_API_KEY"]
BASE    = os.environ["N8N_BASE"]
WID     = "8rTfJPgE7THZfatr"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
WHITELIST = {"executionOrder","errorWorkflow","saveManualExecutions","timezone",
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

wf = req("GET", f"/api/v1/workflows/{WID}")
def node(name): return next(n for n in wf["nodes"] if n["name"] == name)

# 1) List scrape: markdown (default) instead of plain text
n = node("Jina: Scrape Gelbe Seiten")
n["parameters"]["sendHeaders"] = False
n["parameters"].pop("headerParameters", None)

# 2) Parse `## [Name](gsbiz url)` blocks (all-items)
node("Extract Companies")["parameters"]["jsCode"] = r"""const out = [];
const seen = new Set();
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const query = $('Build Search Queries').itemMatching(i).json;
  const raw = items[i].json;
  const text = typeof raw === 'string' ? raw : (raw.body || raw.data || JSON.stringify(raw));

  const RE = /##\s+\[([^\]]{3,90})\]\((https:\/\/www\.gelbeseiten\.de\/gsbiz\/[a-f0-9-]{20,})\)/g;
  let m, count = 0;
  while ((m = RE.exec(text)) !== null && count < 25) {
    const gsUrl = m[2];
    if (seen.has(gsUrl)) continue;
    seen.add(gsUrl);
    count++;
    out.push({ json: {
      company_name: m[1].replace(/\s+/g, ' ').trim(),
      gs_url: gsUrl,
      category: query.category,
      pitch: query.pitch,
      city: query.city,
      input_source: 'prospecting'
    }});
  }
}
return out;"""

# 3) Dedup: pass gs_url through; is_new by company_id only
node("DB: Dedup Check")["parameters"]["query"] = """SELECT
  '{{ $json.company_name.replace(/'/g, "''") }}' as company_name,
  '{{ $json.gs_url }}' as gs_url,
  '{{ $json.category }}' as category,
  '{{ $json.pitch }}' as pitch,
  '{{ $json.city }}' as city,
  NOT EXISTS (
    SELECT 1 FROM jobs
    WHERE company_id = LOWER(REGEXP_REPLACE('{{ $json.company_name.replace(/'/g, "''") }}', '[^a-z0-9]+', '-', 'g'))
  ) as is_new;"""

# 4) Save Prospect: source_url = gsbiz detail URL; RETURNING feeds Enrich
q = node("DB: Save Prospect")["parameters"]["query"]
q = q.replace("'{{ $json.source_url }}',", "'{{ $json.gs_url }}',")
q = q.rstrip().rstrip(";") + "\nRETURNING company_id, source_url;"
assert "RETURNING company_id, source_url;" in q and "$json.gs_url" in q
node("DB: Save Prospect")["parameters"]["query"] = q

# 5) Enrich: fetch gsbiz detail page in markdown
n = node("Enrich: Find Email via Jina")
n["parameters"]["url"] = "=https://r.jina.ai/{{ $json.source_url }}"
n["parameters"]["sendHeaders"] = False
n["parameters"].pop("headerParameters", None)
n["parameters"]["options"]["timeout"] = 25000
n["onError"] = "continueErrorOutput"

# 6) Parse detail page: website link + optional direct email
node("DB: Save Enriched Email")["parameters"]["jsCode"] = r"""const prospect = $('DB: Save Prospect').item.json;
const raw = $input.item.json;
const text = typeof raw === 'string' ? raw : (raw.body || raw.data || '');

const WEB_RE = /\[(?:Zur\s+)?Webseite[^\]]*\]\((https?:\/\/[^)\s"]+)/i;
const ANY_RE = /\((https?:\/\/(?!www\.gelbeseiten|maps\.|www\.google|facebook|instagram|youtube|linkedin|xing)[^)\s"]+)/i;
const EMAIL_RE = /[\w.+\-]+@[\w\-]+\.[\w.\-]{2,}/g;
const BAD_RE = /noreply|no[-_]reply|donotreply|newsletter|gelbeseiten|sentry|example/i;

const webMatch = text.match(WEB_RE) || text.match(ANY_RE);
const website = webMatch ? webMatch[1].replace(/\/$/, '').split('"')[0] : null;
const emails = (text.match(EMAIL_RE) || []).filter(e => !BAD_RE.test(e) && e.length > 6);
const email = emails[0] || null;

return { json: {
  company_id: prospect.company_id || 'unknown',
  website, email,
  found: Boolean(website || email)
} };"""

# 7) Update: write website into source_url, email if present
node("DB: Update Email")["parameters"]["query"] = """UPDATE jobs SET
  contact_email = {{ $json.email ? "'" + $json.email.replace(/'/g, "''") + "'" : 'contact_email' }},
  source_url    = {{ $json.website ? "'" + $json.website.replace(/'/g, "''") + "'" : 'source_url' }},
  updated_at = NOW()
WHERE company_id = '{{ $json.company_id }}' AND {{ $json.found === true ? 'TRUE' : 'FALSE' }};"""

settings = {k: v for k, v in (wf.get("settings") or {}).items() if k in WHITELIST}
req("PUT", f"/api/v1/workflows/{WID}",
    {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": settings})
req("POST", f"/api/v1/workflows/{WID}/deactivate")
print("saved, active =", req("POST", f"/api/v1/workflows/{WID}/activate").get("active"))
