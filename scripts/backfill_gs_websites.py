"""
One-off backfill: for gelbeseiten prospects whose jobs.source_url still points
at the gsbiz detail page, fetch it via Jina (markdown, 1 req / 3.5 s) and write
the real company website into source_url (+ contact_email if present).
Run on VPS host (talks to postgres via docker exec). Env: none needed.
"""
import json, re, subprocess, sys, time, urllib.request

PSQL = ["docker", "exec", "n8n-automation-postgres-1", "psql", "-U", "hub", "-d", "jobradar", "-t", "-A"]

def sql(q):
    return subprocess.run(PSQL + ["-c", q], capture_output=True, text=True).stdout.strip()

rows = sql("""SELECT id || '|' || source_url FROM jobs
WHERE source_url LIKE '%gelbeseiten.de/gsbiz/%'
  AND company_id IN (SELECT company_id FROM companies WHERE meta->>'source'='gelbeseiten');""")
targets = [r.split("|", 1) for r in rows.splitlines() if "|" in r]
print(f"backfill targets: {len(targets)}", flush=True)

WEB_RE = re.compile(r'\[(?:Zur\s+)?Webseite[^\]]*\]\((https?://[^)\s"]+)', re.I)
ANY_RE = re.compile(r'\((https?://(?!www\.gelbeseiten|maps\.|www\.google|facebook|instagram|youtube|linkedin|xing)[^)\s"]+)', re.I)
EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+\.[\w.\-]{2,}')
BAD_RE = re.compile(r'noreply|no[-_]reply|donotreply|newsletter|gelbeseiten|sentry|example', re.I)

ok = fail = 0
for i, (job_id, gs_url) in enumerate(targets):
    try:
        with urllib.request.urlopen(f"https://r.jina.ai/{gs_url}", timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
        m = WEB_RE.search(text) or ANY_RE.search(text)
        website = m.group(1).rstrip("/").split('"')[0] if m else None
        emails = [e for e in EMAIL_RE.findall(text) if not BAD_RE.search(e) and len(e) > 6]
        email = emails[0] if emails else None
        if website or email:
            sets = ["updated_at = NOW()"]
            if website: sets.append("source_url = '" + website.replace("'", "''") + "'")
            if email:   sets.append("contact_email = '" + email.replace("'", "''") + "'")
            sql(f"UPDATE jobs SET {', '.join(sets)} WHERE id = '{job_id}'::uuid;")
            ok += 1
        else:
            fail += 1
    except Exception:
        fail += 1
    if (i + 1) % 50 == 0:
        print(f"progress {i+1}/{len(targets)}: ok={ok} miss={fail}", flush=True)
    time.sleep(3.5)

print(f"DONE: updated={ok} missed={fail} of {len(targets)}", flush=True)
