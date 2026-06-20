import json, os, sys, re

SANITIZER = (
    "// UTF-8 sanitizer: replace malformed chars before processing\n"
    "function sanitizeText(s) {\n"
    "  if (!s) return s;\n"
    "  return String(s)\n"
    "    .replace(/\\uFFFD/g, '')   // replacement char\n"
    "    .replace(/\\u0000/g, '')   // null bytes\n"
    "    .trim();\n"
    "}\n\n"
)

DEPLOYED = [
    ('n8n/gmail-flow-api.json',         'JRXuonKppWpNM3UB'),
    ('n8n/mailde-flow-api.json',        'crCYiC5LUCvCyeIQ'),
    ('n8n/firecrawl-flow-api.json',     '8nSk6jvOSNofvLBu'),
    ('n8n/corporate-flow-import.json',  '2ZmgiT4IhqzObByh'),
    ('n8n/job-apis-flow-api.json',      'HDJIQgfBv2Coa4jo'),
    ('n8n/gewerbe-flow-api.json',       'VBfS8H71yz0ArkWT'),
]

def load(path):
    for enc in ['utf-8', 'utf-8-sig']:
        try:
            with open(path, encoding=enc) as f:
                raw = f.read()
            # Strip lone surrogates (invalid JSON/unicode) — both \uD800 escape form and actual chars
            raw = re.sub(r'\\ud[89aAbB][0-9a-fA-F]{2}', '', raw)  # JSON escape form
            raw = re.sub(r'[\ud800-\udfff]', '', raw)              # actual surrogate chars
            return json.loads(raw)
        except Exception:
            pass
    return None

def save_payload(flow_id, d):
    payload = {
        'name': d['name'],
        'nodes': d['nodes'],
        'connections': d['connections'],
        'settings': d.get('settings', {'executionOrder': 'v1'})
    }
    out = f'scripts/deploy_payloads/{flow_id}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out

for path, flow_id in DEPLOYED:
    d = load(path)
    if not d:
        print(f'FAILED TO LOAD: {path}')
        continue

    changed = False
    for node in d['nodes']:
        name = node.get('name', '')
        if 'Normalize' in name and node.get('type') == 'n8n-nodes-base.code':
            code = node['parameters'].get('jsCode', '')
            if code and 'sanitizeText' not in code:
                node['parameters']['jsCode'] = SANITIZER + code
                changed = True
                print(f'Sanitizer added: {os.path.basename(path)} / {name}')

    # Write payload (includes Filter: Skip Expired from previous step)
    try:
        out = save_payload(flow_id, d)
        if changed:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        print(f'  Payload: {out}')
    except Exception as e:
        print(f'  ERROR: {e}')

print('Done')
