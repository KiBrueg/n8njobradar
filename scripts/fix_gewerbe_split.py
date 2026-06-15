import json

path = 'n8n/gewerbe-flow-api.json'
with open(path, encoding='utf-8') as f:
    d = json.load(f)

new_code = """// Split listing page into individual project items.
// Method 1: markdown [text](url)
// Method 2: bare https:// URLs
// Method 3: href="url" in raw HTML
// Fallback: pass full page with unique daily key (avoids dedup block)

const LISTING_LABELS = [
  'xing-projekte-python',
  'freelancermap-python',
  'gulp-python-remote',
  'malt-python-remote',
  'freelancede-python'
];

const scrape = $input.item.json;
const target = $('Scrape Targets').item.json;
const label  = target.label || '';

if (!LISTING_LABELS.includes(label)) {
  return [{ json: scrape }];
}

const markdown = (scrape.data && scrape.data.markdown) || '';
const rawHtml  = (scrape.data && scrape.data.html) || '';
const text     = markdown || rawHtml;

// URL filters per platform
const patterns = {
  'xing-projekte-python':  u => u.includes('xing.com/projekte/') && !u.includes('/search') && !u.includes('?keywords'),
  'freelancermap-python':  u => u.includes('freelancermap.de/') && (u.includes('/projekt/') || u.includes('projektboerse')),
  'gulp-python-remote':    u => u.includes('gulp.de/') && (u.includes('/project/') || u.includes('/projekte/')),
  'malt-python-remote':    u => u.includes('malt.de/') && (u.includes('/project/') || u.includes('/profile/') || u.includes('/mission/')),
  'freelancede-python':    u => u.includes('freelance.de/Projekte/') || (u.includes('freelance.de/') && u.includes('id='))
};

const filterFn = patterns[label] || (() => false);
const seen = new Set();
const jobLinks = [];

// Method 1: Markdown [text](url)
const mdPattern = /\\[([^\\]\\n]+)\\]\\((https?:\\/\\/[^\\)\\s\\n]{10,})\\)/g;
let m;
while ((m = mdPattern.exec(text)) !== null) {
  const url = m[2].trim();
  if (!seen.has(url) && filterFn(url)) {
    seen.add(url);
    jobLinks.push({ title: m[1].trim(), url });
  }
}

// Method 2: Bare URLs
if (jobLinks.length < 3) {
  const barePattern = /https?:\\/\\/[^\\s\\n\\)\\]"'<>{},]{15,}/g;
  let b;
  while ((b = barePattern.exec(text)) !== null) {
    const url = b[0].replace(/[.,;:!?]+$/, '');
    if (!seen.has(url) && filterFn(url)) {
      seen.add(url);
      jobLinks.push({ title: url.split('/').pop() || url, url });
    }
  }
}

// Method 3: href="..." patterns
if (jobLinks.length < 3) {
  const hrefPattern = /href="(https?:\\/\\/[^"]{10,})"/g;
  let h;
  while ((h = hrefPattern.exec(rawHtml || text)) !== null) {
    const url = h[1].trim();
    if (!seen.has(url) && filterFn(url)) {
      seen.add(url);
      jobLinks.push({ title: url.split('/').pop() || url, url });
    }
  }
}

const MAX_PER_PAGE = 25;
const selected = jobLinks.slice(0, MAX_PER_PAGE);

// Fallback: no individual links found — pass full page with unique daily key
if (selected.length === 0) {
  const todayKey = label + '::' + new Date().toISOString().substring(0, 10);
  return [{
    json: {
      ...scrape,
      _fallback: true,
      data: {
        ...(scrape.data || {}),
        metadata: {
          ...((scrape.data && scrape.data.metadata) || {}),
          sourceURL: 'https://gewerbe-daily/' + todayKey,
          platform: label
        }
      }
    }
  }];
}

const lines = text.split('\\n');

return selected.map(({ title, url }) => {
  const pos      = text.indexOf(url);
  const lineNum  = pos >= 0 ? (text.substring(0, pos).match(/\\n/g) || []).length : 0;
  const ctxStart = Math.max(0, lineNum - 2);
  const ctxEnd   = Math.min(lines.length, lineNum + 20);
  const ctx = lines.slice(ctxStart, ctxEnd)
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('!['));

  return {
    json: {
      success: true,
      data: {
        markdown: ctx.join('\\n').substring(0, 5000),
        metadata: { sourceURL: url, title, platform: label }
      }
    }
  };
});"""

for node in d['nodes']:
    if node['name'] == 'Split: Project Listings':
        node['parameters']['jsCode'] = new_code
        print('Updated Split: Project Listings')
        print(f'Code length: {len(new_code)} chars')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

payload = {'name': d['name'], 'nodes': d['nodes'], 'connections': d['connections'], 'settings': d.get('settings', {'executionOrder': 'v1'})}
with open('scripts/deploy_payloads/VBfS8H71yz0ArkWT.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False)

print('Done')
