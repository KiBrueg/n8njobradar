/**
 * make-corporate-flow.js
 * Generates Flow 2b: Corporate Career Pages
 *
 * Sources:
 * Tier 1 - Greenhouse API (free public API, no auth)
 * Tier 2 - Lever API (free public API, no auth)
 * Tier 3 - Direct HTTP JSON APIs (Zalando, Check24)
 * Tier 4 - Firecrawl stubs (SAP, Siemens - JS-rendered, activate when needed)
 */

const fs = require('fs');
const path = require('path');

// ── Greenhouse companies ────────────────────────────────────────────────────
const GREENHOUSE_COMPANIES = [
  { slug: 'celonis',      label: 'Celonis',      note: 'Process Mining/Automation, Munich' },
  { slug: 'hellofresh',  label: 'HelloFresh',   note: 'Tech/Operations, Berlin' },
  { slug: 'n26',         label: 'N26',          note: 'Fintech, Berlin' },
  { slug: 'getyourguide', label: 'GetYourGuide', note: 'Travel Tech, Berlin' },
  { slug: 'sumup',       label: 'SumUp',        note: 'Fintech/Payments, Berlin' },
  { slug: 'babbel',      label: 'Babbel',       note: 'EdTech/Language, Berlin' },
  { slug: 'contentful',  label: 'Contentful',   note: 'Headless CMS, Berlin' },
];

// ── Lever companies ─────────────────────────────────────────────────────────
const LEVER_COMPANIES = [
  { slug: 'aleph-alpha',  label: 'Aleph Alpha',     note: 'AI Research, Heidelberg' },
];

// ── Direct HTTP (JSON APIs) ─────────────────────────────────────────────────
const DIRECT_HTTP = [];

// ── Firecrawl stubs (activate later) ───────────────────────────────────────
const FIRECRAWL_STUBS = [
  { id: 'sap',          label: 'SAP Jobs',          note: 'Activate: jobs.sap.com/search/?q=automation+engineer' },
  { id: 'siemens',      label: 'Siemens Jobs',      note: 'Activate: jobs.siemens.com/?keywords=automation' },
  { id: 'deliveryhero', label: 'Delivery Hero Jobs', note: 'Activate: careers.deliveryhero.com (custom ATS)' },
  { id: 'teamviewer',   label: 'TeamViewer Jobs',   note: 'Activate: teamviewer.com/en/company/careers (custom ATS)' },
  { id: 'zalando',      label: 'Zalando Jobs',      note: 'Activate: jobs.zalando.com -- no public API, needs Firecrawl' },
];

// ── Keyword filter (applied before LLM to save tokens) ─────────────────────
// Strict AI/automation focus — jobs without these keywords are discarded.
// Broad terms (engineer, developer, software, backend, cloud) intentionally
// excluded to avoid sending irrelevant postings to the LLM.
const KEYWORDS = [
  // Automation (EN/DE)
  'automation', 'automat', 'rpa', 'robotic process', 'process automation',
  'workflow automation', 'low-code', 'no-code',
  // AI / ML (English)
  'machine learning', 'deep learning', 'neural network',
  'artificial intelligence',
  'ai engineer', 'ai developer', 'ai specialist', 'ai researcher', 'ai architect',
  'llm', 'large language model', 'generative ai', 'genai', 'gen-ai',
  'prompt engineer', 'vector search', 'rag ',
  // AI / ML (German)
  'künstliche intelligenz', 'ki engineer', 'ki developer', 'ki-', ' ki ',
  'maschinelles lernen', 'automatisierung',
  // Data Engineering / MLOps
  'mlops', 'dataops', 'data engineer', 'data pipeline', 'etl',
  // Workflow / integration tools (strong signal)
  'n8n', 'zapier', 'airflow', 'prefect', 'dagster', 'make.com',
  'integration engineer', 'integration developer',
  // DevOps / Platform (often automation-adjacent)
  'devops', 'platform engineer',
  // Process intelligence
  'process mining',
];

// ── Exclusion filter ─────────────────────────────────────────────────────────
// Jobs matching these are discarded even if they contain AI/automation keywords.
// Checked against title only (to avoid false positives from job description text).
const EXCLUDE_TITLE_KW = [
  'senior ', 'sr. ', 'sr ',
  'staff engineer', 'principal ',
  'lead engineer', 'tech lead', 'engineering lead',
  'head of', 'director', 'vp ', 'vice president',
];
// Regex checked against full text: filters out "5+ years of experience" requirements.
// Matches: "5 years experience", "6+ Jahre Berufserfahrung", "10 years of experience" etc.
const EXCLUDE_EXP_REGEX_SRC =
  '\\\\b([5-9]|\\\\d{2})\\\\+?\\\\s*(?:years?|jahre?)(?:\\\\s+of)?\\\\s*(?:experience|erfahrung|berufserfahrung)';

// ══════════════════════════════════════════════════════════════════════════════
// Node builders
// ══════════════════════════════════════════════════════════════════════════════

let xPos = 200;
const Y_CENTER = 300;
const STEP = 220;

function pos(col, row = 0) {
  return [200 + col * STEP, Y_CENTER + row * 200];
}

// Schedule trigger
const triggerNode = {
  id: 'n_trigger',
  name: 'Schedule: Daily 05:00',
  type: 'n8n-nodes-base.scheduleTrigger',
  typeVersion: 1.1,
  position: pos(0),
  parameters: {
    rule: {
      interval: [{ field: 'cronExpression', expression: '0 5 * * *' }]
    }
  },
  notes: 'Runs at 05:00 CET daily. After Flow 2 (04:00) to avoid DB contention.'
};

// ── Greenhouse fetch nodes ──────────────────────────────────────────────────
function greenhouseNode(company, col, row) {
  return {
    id: `n_gh_${company.slug.replace(/-/g, '_')}`,
    name: `GH: ${company.label}`,
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col, row),
    notes: company.note,
    onError: 'continueErrorOutput',
    parameters: {
      method: 'GET',
      url: `https://boards-api.greenhouse.io/v1/boards/${company.slug}/jobs?content=true`,
      options: { timeout: 15000 }
    }
  };
}

function greenhouseFlattenNode(company, col, row) {
  return {
    id: `n_gh_flat_${company.slug.replace(/-/g, '_')}`,
    name: `Flatten: GH ${company.label}`,
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, row),
    parameters: {
      jsCode: `const resp = $input.first().json;
const jobs = Array.isArray(resp.jobs) ? resp.jobs : [];
return jobs.map(j => ({ json: {
  _source: 'greenhouse_api',
  _company: '${company.label}',
  _company_slug: '${company.slug}',
  title: j.title || '',
  location: (j.location && j.location.name) || 'Remote',
  url: j.absolute_url || '',
  published_at: j.updated_at || null,
  departments: Array.isArray(j.departments) ? j.departments.map(d => d.name).join(', ') : '',
  content: j.content ? j.content.replace(/<[^>]+>/g, ' ').substring(0, 3000) : ''
} }));`
    }
  };
}

// ── Lever fetch nodes ───────────────────────────────────────────────────────
function leverNode(company, col, row) {
  return {
    id: `n_lv_${company.slug.replace(/-/g, '_')}`,
    name: `Lever: ${company.label}`,
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col, row),
    notes: company.note,
    onError: 'continueErrorOutput',
    parameters: {
      method: 'GET',
      url: `https://api.lever.co/v0/postings/${company.slug}?mode=json`,
      options: { timeout: 15000 }
    }
  };
}

function leverFlattenNode(company, col, row) {
  return {
    id: `n_lv_flat_${company.slug.replace(/-/g, '_')}`,
    name: `Flatten: Lever ${company.label}`,
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, row),
    parameters: {
      jsCode: `const jobs = Array.isArray($input.first().json) ? $input.first().json : [];
return jobs.map(j => ({ json: {
  _source: 'lever_api',
  _company: '${company.label}',
  _company_slug: '${company.slug}',
  title: j.text || '',
  location: (j.categories && j.categories.location) || 'Remote',
  url: j.hostedUrl || '',
  published_at: j.createdAt ? new Date(j.createdAt).toISOString() : null,
  departments: (j.categories && j.categories.department) || '',
  content: j.descriptionPlain ? j.descriptionPlain.substring(0, 3000) : ''
} }));`
    }
  };
}

// ── Direct HTTP nodes ───────────────────────────────────────────────────────
function directHttpNode(company, col, row) {
  return {
    id: `n_http_${company.id}`,
    name: `HTTP: ${company.label}`,
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col, row),
    notes: company.note,
    onError: 'continueErrorOutput',
    parameters: {
      method: 'GET',
      url: company.url,
      options: { timeout: 15000 }
    }
  };
}

function directHttpFlattenNode(company, col, row) {
  return {
    id: `n_http_flat_${company.id}`,
    name: `Flatten: ${company.label}`,
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, row),
    parameters: {
      jsCode: `// ${company.label} API response normalization
// Adjust field names if API structure changes
const resp = $input.item.json;
const jobs = Array.isArray(resp.results) ? resp.results :
             Array.isArray(resp.jobs) ? resp.jobs :
             Array.isArray(resp) ? resp : [];
return jobs.map(j => ({ json: {
  _source: '${company.source_detail}',
  _company: '${company.label}',
  title: j.title || j.job_title || j.name || '',
  location: j.location || j.city || 'Unknown',
  url: j.url || j.link || j.apply_url || '',
  published_at: j.published_at || j.created_at || j.date || null,
  departments: j.department || j.team || j.category || '',
  content: (j.description || j.summary || '').replace(/<[^>]+>/g, ' ').substring(0, 3000)
} }));`
    }
  };
}

// ── Firecrawl stub nodes ────────────────────────────────────────────────────
function firecrawlStubNode(company, col, row) {
  return {
    id: `n_fc_stub_${company.id}`,
    name: `STUB: ${company.label}`,
    type: 'n8n-nodes-base.noOp',
    typeVersion: 1,
    position: pos(col, row),
    notes: company.note + '\nReplace with Firecrawl HTTP node when ready.'
  };
}

// ── Merge node ──────────────────────────────────────────────────────────────
const TOTAL_INPUTS = GREENHOUSE_COMPANIES.length + LEVER_COMPANIES.length + DIRECT_HTTP.length;

function mergeNode(col) {
  return {
    id: 'n_merge',
    name: 'Merge: All Corporate',
    type: 'n8n-nodes-base.merge',
    typeVersion: 3,
    position: pos(col),
    parameters: {
      mode: 'append',
      numberInputs: TOTAL_INPUTS
    }
  };
}

// ── Keyword filter (Code node before LLM) ──────────────────────────────────
function keywordFilterNode(col) {
  const kwList = KEYWORDS.map(k => `'${k}'`).join(', ');
  const exList = EXCLUDE_TITLE_KW.map(k => `'${k}'`).join(', ');
  return {
    id: 'n_kw_filter',
    name: 'Keyword Filter',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col),
    notes: 'Keeps AI/automation jobs. Discards: senior/lead/head roles; 5+ years experience requirements.',
    parameters: {
      jsCode: `const KEYWORDS = [${kwList}];
const EXCLUDE_TITLE = [${exList}];
const EXP_REGEX = new RegExp('${EXCLUDE_EXP_REGEX_SRC}', 'i');

return $input.all().filter(item => {
  const job = item.json;
  const title = (job.title || '').toLowerCase();
  const fullText = [title, (job.departments || ''), (job.content || '')].join(' ').toLowerCase();

  // Discard senior/lead/head/director titles
  if (EXCLUDE_TITLE.some(ex => title.includes(ex))) return false;
  // Discard postings requiring 5+ years of experience
  if (EXP_REGEX.test(fullText)) return false;
  // Keep only AI/automation-relevant roles
  return KEYWORDS.some(kw => fullText.includes(kw));
});`
    }
  };
}

// ── Normalize node ──────────────────────────────────────────────────────────
function normalizeNode(col) {
  return {
    id: 'n_normalize',
    name: 'Normalize: Corporate Job',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col),
    parameters: {
      jsCode: `const now = new Date().toISOString();
return $input.all().map(item => {
  const j = item.json;
  return { json: {
    normalized_input: {
      input_source: 'scraped',
      source_detail: j._source || 'corporate_api',
      email_account_id: null,
      email_address: null,
      email_provider: null,
      subject: '[JOB POSTING] ' + (j.title || '') + ' @ ' + (j._company || ''),
      date: now,
      raw_text: [
        '=== JOB POSTING FROM CORPORATE CAREER PAGE ===',
        'Source: ' + (j._source || 'corporate_api'),
        'Company: ' + (j._company || ''),
        'Position: ' + (j.title || ''),
        'Location: ' + (j.location || ''),
        'Department: ' + (j.departments || ''),
        'URL: ' + (j.url || ''),
        '',
        '=== JOB DESCRIPTION ===',
        j.content || ''
      ].join('\\n').substring(0, 8000),
      raw_meta: {
        company: j._company || null,
        company_slug: j._company_slug || null,
        job_url: j.url || null,
        published_at: j.published_at || null,
        source: j._source || null
      }
    }
  } };
});`
    }
  };
}

// ── Dedup Check ─────────────────────────────────────────────────────────────
function dedupNode(col) {
  return {
    id: 'n_dedup',
    name: 'Dedup Check',
    type: 'n8n-nodes-base.postgres',
    typeVersion: 2.5,
    position: pos(col),
    credentials: { postgres: { id: 'ZjjVGIqiRAUVlCk6', name: 'radar' } },
    parameters: {
      operation: 'executeQuery',
      query: `SELECT COUNT(*) AS cnt
FROM jobs
WHERE source_url = {{ $json.normalized_input.raw_meta.job_url
  ? "'" + $json.normalized_input.raw_meta.job_url.replace(/'/g,"''").substring(0,200) + "'"
  : "'__no_url__'" }}
  AND updated_at > NOW() - INTERVAL '7 days';`,
      options: {}
    }
  };
}

// ── IF: not already processed ───────────────────────────────────────────────
function ifNotProcessedNode(col) {
  return {
    id: 'n_if_dedup',
    name: 'IF: not already processed',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
        conditions: [{
          id: 'cond_dedup',
          leftValue: '={{ $json.cnt }}',
          rightValue: '0',
          operator: { type: 'string', operation: 'equals' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── LLM Call ────────────────────────────────────────────────────────────────
function llmNode(col) {
  return {
    id: 'n_llm',
    name: 'LLM Call (OpenRouter)',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col),
    parameters: {
      method: 'POST',
      url: 'https://openrouter.ai/api/v1/chat/completions',
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: 'Authorization', value: '=Bearer {{ $env.OPENROUTER_API_KEY }}' },
          { name: 'content-type', value: 'application/json' }
        ]
      },
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: "={{ JSON.stringify({ model: 'qwen/qwen3-30b-a3b-instruct-2507', max_tokens: 1500, messages: [{ role: 'system', content: $env.JOBRADAR_SYSTEM_PROMPT }, { role: 'user', content: '/no_think\\n\\nCONTEXT: This is a job posting scraped from a corporate career page API (Greenhouse/Lever). Extract ALL available fields: company_name from raw_meta.company, job_title from subject or raw_text Position field, location, tech_stack, key_requirements, source_url from raw_meta.job_url. Set category=job_posting, is_job_related=true, action=create_job. Evaluate relevance_score per candidate profile. Output JSON only.\\n\\n' + JSON.stringify($json.normalized_input) }] }) }}",
      options: { timeout: 60000 }
    }
  };
}

// ── Parse LLM Response ──────────────────────────────────────────────────────
function parseNode(col) {
  return {
    id: 'n_parse',
    name: 'Parse LLM Response',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col),
    parameters: {
      jsCode: `const body = $input.item.json;
let jobEvent;
try {
  let raw = (body.choices[0].message.content || '').trim();
  raw = raw.replace(/<think>[\\s\\S]*?<\\/think>/gi, '').trim();
  raw = raw.replace(/^\`\`\`(?:json)?\\s*/i, '').replace(/\\s*\`\`\`$/, '').trim();
  jobEvent = JSON.parse(raw);
} catch (err) {
  throw new Error('LLM returned invalid JSON: ' + String(body?.choices?.[0]?.message?.content || '').substring(0, 300));
}

if (typeof jobEvent.is_job_related !== 'boolean') throw new Error('is_job_related must be boolean');
if (typeof jobEvent.injection_suspected !== 'boolean') jobEvent.injection_suspected = false;

const ALLOWED_ACTIONS = ['create_job','update_stage','add_interview','add_deadline','log_only','flag_error','ignore'];
if (!ALLOWED_ACTIONS.includes(jobEvent.action)) throw new Error('Invalid action: ' + String(jobEvent.action));

if (!Array.isArray(jobEvent.tech_stack)) jobEvent.tech_stack = [];
if (!Array.isArray(jobEvent.key_requirements)) jobEvent.key_requirements = [];

const JOB_RELATED_CATEGORIES = ['job_posting','hr_invite','interview_invite','test_task','offer','rejection','follow_up','platform_notification','manual_note'];
if (JOB_RELATED_CATEGORIES.includes(jobEvent.category)) jobEvent.is_job_related = true;

jobEvent.is_job_related_str = jobEvent.is_job_related ? 'yes' : 'no';

return [{ json: { job_event: jobEvent } }];`
    }
  };
}

// ── IF: is_job_related ──────────────────────────────────────────────────────
function ifJobRelatedNode(col) {
  return {
    id: 'n_if_related',
    name: 'IF: is_job_related',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
        conditions: [{
          id: 'cond_related',
          leftValue: '={{ $json.job_event.is_job_related_str }}',
          rightValue: 'yes',
          operator: { type: 'string', operation: 'equals' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── Stop node ───────────────────────────────────────────────────────────────
function stopNode(id, name, col, row) {
  return {
    id,
    name,
    type: 'n8n-nodes-base.noOp',
    typeVersion: 1,
    position: pos(col, row)
  };
}

// ── Prepare DB Params ───────────────────────────────────────────────────────
function prepareDbNode(col) {
  return {
    id: 'n_prepare',
    name: 'Prepare DB Params',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col),
    parameters: {
      jsCode: `const e = $input.first().json.job_event;
const ni = $('Normalize: Corporate Job').first().json.normalized_input;

function sql(v) { if (v===null||v===undefined) return 'NULL'; return "'"+ String(v).replace(/'/g,"''") +"'"; }
function num(v) { if (v===null||v===undefined) return 'NULL'; const n=parseFloat(v); return isNaN(n)?'NULL':String(n); }
function bool(v) { return v===true?'TRUE':'FALSE'; }
function dt(v)   { return v?"'"+ String(v).replace(/'/g,"''") +"'":'NULL'; }
function en(v,t) { return v?"'"+ String(v).replace(/'/g,"''") +"'::"+t:'NULL'; }
function arr(vals) {
  if (!vals||vals.length===0) return "'{}'";
  const parts=vals.map(v=>'"'+ String(v).replace(/\\\\/g,'\\\\\\\\').replace(/"/g,'\\\\"') +'"');
  return "'"+'{'+ parts.join(',') +'}'+"'";
}
function jsonb(v) { if (!v) return "'{}'::jsonb"; return "'"+ JSON.stringify(v).replace(/'/g,"''") +"'::jsonb"; }
function slugify(s) { return (s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''); }

// Fallbacks: use raw_meta structured data when LLM returns null
const titleFromSubject = (ni.subject||'').replace(/^\\[JOB POSTING\\]\\s*/i,'').split(' @ ')[0].trim() || null;
const companyId   = e.company_id   || ni.raw_meta.company_slug || slugify(ni.raw_meta.company) || 'unknown';
const companyName = e.company_name || ni.raw_meta.company      || 'Unknown Company';
const jobTitle    = e.job_title    || titleFromSubject          || null;
const sourceUrl   = e.source_url   || ni.raw_meta.job_url      || null;
const jobIdFuzzy  = e.job_id_fuzzy || [companyId, slugify(jobTitle||'unknown'), slugify(e.location||'unknown')].join('__');

return [{ json: {
  job_event: e,
  resolved: {
    company_id:   companyId,
    company_name: companyName,
    job_title:    jobTitle,
    source_url:   sourceUrl,
    job_id_fuzzy: jobIdFuzzy
  },
  db: {
    company_id_sql:           sql(companyId),
    company_name_sql:         sql(companyName),
    employer_id_sql:          sql(e.employer_id),
    employer_name_sql:        sql(e.employer_name),
    job_id_fuzzy_sql:         sql(jobIdFuzzy),
    job_title_sql:            sql(jobTitle),
    location_sql:             sql(e.location),
    job_thread_key_sql:       sql(e.job_thread_key),
    seniority_sql:            en(e.seniority,'seniority_enum'),
    work_mode_sql:            en(e.work_mode,'work_mode_enum'),
    work_mode_raw_sql:        sql(e.work_mode_raw),
    working_hours_sql:        sql(e.working_hours),
    salary_currency_sql:      sql(e.salary_currency),
    salary_min_sql:           num(e.salary_min),
    salary_max_sql:           num(e.salary_max),
    salary_period_sql:        en(e.salary_period,'salary_period_enum'),
    tech_stack_sql:           arr(e.tech_stack),
    key_requirements_sql:     arr(e.key_requirements),
    current_stage_sql:        en(e.stage||'discovered','job_stage_enum'),
    priority_sql:             en(e.priority,'priority_enum'),
    priority_level_sql:       num(e.priority_level),
    interview_date_sql:       dt(e.interview_date),
    response_deadline_sql:    dt(e.response_deadline),
    application_deadline_sql: dt(e.application_deadline),
    has_had_call_sql:         bool(e.has_had_call),
    call_count_sql:           String(e.call_count||0),
    last_call_date_sql:       dt(e.last_call_date),
    source_url_sql:           sql(sourceUrl),
    source_input_sql:         en('scraped','input_source_enum'),
    summary_sql:              sql(e.summary),
    category_sql:             en(e.category,'job_category_enum'),
    action_sql:               sql(e.action),
    is_job_related_sql:       bool(e.is_job_related),
    call_platform_sql:        en(e.call_platform,'call_platform_enum'),
    call_platform_raw_sql:    sql(e.call_platform_raw),
    raw_text_sql:             sql(ni.raw_text),
    parsed_json_sql:          jsonb(e),
    email_account_id_sql:     sql(null),
    raw_reference_sql:        sql(ni.raw_meta.job_url),
    email_date_sql:           dt(ni.date),
    sender_risk_level_sql:    sql('low'),
    sender_risk_signals_sql:  arr([])
  }
} }];`
    }
  };
}

// ── DB Write ────────────────────────────────────────────────────────────────
function dbWriteNode(col) {
  return {
    id: 'n_db_write',
    name: 'DB: Write All',
    type: 'n8n-nodes-base.postgres',
    typeVersion: 2.5,
    position: pos(col),
    credentials: { postgres: { id: 'ZjjVGIqiRAUVlCk6', name: 'radar' } },
    parameters: {
      operation: 'executeQuery',
      query: `WITH
co AS (
  INSERT INTO companies (company_id, name, meta)
  VALUES ({{ $json.db.company_id_sql }}, {{ $json.db.company_name_sql }}, '{}')
  ON CONFLICT (tenant_id, company_id) DO UPDATE SET updated_at = NOW()
  RETURNING id
),
j AS (
  INSERT INTO jobs (
    job_id_fuzzy, company_id, employer_id,
    job_title, location, seniority,
    work_mode, work_mode_raw, working_hours,
    salary_currency, salary_min, salary_max, salary_period,
    tech_stack, key_requirements,
    current_stage, priority, priority_level,
    interview_date, response_deadline, application_deadline,
    has_had_call, call_count, last_call_date,
    source_url, source_input, summary
  ) VALUES (
    {{ $json.db.job_id_fuzzy_sql }}, {{ $json.db.company_id_sql }}, {{ $json.db.employer_id_sql }},
    {{ $json.db.job_title_sql }}, {{ $json.db.location_sql }}, {{ $json.db.seniority_sql }},
    {{ $json.db.work_mode_sql }}, {{ $json.db.work_mode_raw_sql }}, {{ $json.db.working_hours_sql }},
    {{ $json.db.salary_currency_sql }}, {{ $json.db.salary_min_sql }}, {{ $json.db.salary_max_sql }}, {{ $json.db.salary_period_sql }},
    {{ $json.db.tech_stack_sql }}, {{ $json.db.key_requirements_sql }},
    {{ $json.db.current_stage_sql }}, {{ $json.db.priority_sql }}, {{ $json.db.priority_level_sql }},
    {{ $json.db.interview_date_sql }}, {{ $json.db.response_deadline_sql }}, {{ $json.db.application_deadline_sql }},
    {{ $json.db.has_had_call_sql }}, {{ $json.db.call_count_sql }}, {{ $json.db.last_call_date_sql }},
    {{ $json.db.source_url_sql }}, {{ $json.db.source_input_sql }}, {{ $json.db.summary_sql }}
  )
  ON CONFLICT (tenant_id, job_id_fuzzy) DO UPDATE SET
    current_stage = EXCLUDED.current_stage,
    priority = EXCLUDED.priority,
    summary = EXCLUDED.summary,
    updated_at = NOW()
  RETURNING id, job_id_fuzzy, current_stage::text, priority::text, summary
),
ev AS (
  INSERT INTO job_events (
    job_id, job_id_fuzzy, input_source, source_detail,
    category, is_job_related, action,
    stage, priority, priority_level,
    raw_text, parsed_json,
    email_account_id, raw_reference, email_date,
    sender_risk_level, sender_risk_signals
  )
  SELECT
    (SELECT id FROM j), {{ $json.db.job_id_fuzzy_sql }},
    {{ $json.db.source_input_sql }}, {{ $json.db.raw_reference_sql }},
    {{ $json.db.category_sql }}, {{ $json.db.is_job_related_sql }}, {{ $json.db.action_sql }},
    {{ $json.db.current_stage_sql }}, {{ $json.db.priority_sql }}, {{ $json.db.priority_level_sql }},
    {{ $json.db.raw_text_sql }}, {{ $json.db.parsed_json_sql }},
    {{ $json.db.email_account_id_sql }}, {{ $json.db.raw_reference_sql }}, {{ $json.db.email_date_sql }},
    {{ $json.db.sender_risk_level_sql }}, {{ $json.db.sender_risk_signals_sql }}
  RETURNING id
)
SELECT
  (SELECT id FROM j) AS job_id,
  (SELECT job_id_fuzzy FROM j) AS job_id_fuzzy,
  (SELECT current_stage FROM j) AS stage,
  (SELECT priority FROM j) AS priority,
  (SELECT summary FROM j) AS summary,
  (SELECT id FROM ev) AS event_id;`,
      options: {}
    }
  };
}

// ── IF: has interview_date ──────────────────────────────────────────────────
function ifInterviewDateNode(col) {
  return {
    id: 'n_if_interview',
    name: 'IF: has interview_date',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col, -2),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose', version: 2 },
        conditions: [{
          id: 'cond_interview',
          leftValue: "={{ $('Prepare DB Params').first().json.job_event.interview_date }}",
          rightValue: '',
          operator: { type: 'string', operation: 'isNotEmpty' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── Google Calendar: Interview ───────────────────────────────────────────────
function calendarInterviewNode(col) {
  return {
    id: 'n_cal_interview',
    name: 'Google Calendar: Interview',
    type: 'n8n-nodes-base.googleCalendar',
    typeVersion: 1.3,
    position: pos(col, -2),
    credentials: { googleCalendarOAuth2Api: { id: 'eLQTxfMJ6kryO1Iy', name: 'Google Calendar' } },
    parameters: {
      operation: 'create',
      calendar: { __rl: true, value: 'primary', mode: 'list' },
      title: "={{ '\\uD83C\\uDFAF Interview: ' + ($('Prepare DB Params').first().json.resolved.job_title || 'Position') + ' @ ' + ($('Prepare DB Params').first().json.resolved.company_name || 'Company') }}",
      start: "={{ ($('Prepare DB Params').first().json.job_event.interview_date || '').substring(0, 10) + 'T10:00:00' }}",
      end:   "={{ ($('Prepare DB Params').first().json.job_event.interview_date || '').substring(0, 10) + 'T11:00:00' }}",
      additionalFields: {
        description: "={{ ($('Prepare DB Params').first().json.job_event.summary || '') + '\\n\\n' + ($('Prepare DB Params').first().json.resolved.source_url || '') }}"
      }
    }
  };
}

// ── Enrich: add resolved fields to DB output (per-item) ─────────────────────
// Uses index-match against Prepare DB Params (.all()) to avoid paired-item issues.
function enrichNode(col) {
  return {
    id: 'n_enrich',
    name: 'Enrich: Add Resolved Fields',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, 2),
    parameters: {
      jsCode: `const allPrep = $('Prepare DB Params').all();
return $input.all().map((item, i) => {
  const prep = allPrep[i] ? allPrep[i].json : {};
  const res = prep.resolved  || {};
  const ev  = prep.job_event || {};
  // Fallback: passed keyword filter = at least moderate relevance.
  // LLM often returns null for relevance_score on scraped postings.
  const score = ev.relevance_score || 50;
  const prio  = ev.priority || (score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low');
  return { json: {
    company_name:    res.company_name || null,
    job_title:       res.job_title    || null,
    source_url:      res.source_url   || null,
    relevance_score: score,
    priority:        prio,
    location:        ev.location  || null,
    work_mode:       ev.work_mode || null
  }};
});`
    }
  };
}

// ── Aggregate: collect all enriched jobs ─────────────────────────────────────
function aggregateNode(col) {
  return {
    id: 'n_aggregate',
    name: 'Aggregate: All Jobs',
    type: 'n8n-nodes-base.aggregate',
    typeVersion: 1,
    position: pos(col, 2),
    parameters: {
      aggregate: 'aggregateAllItemData',
      destinationFieldName: 'jobs',
      options: {}
    }
  };
}

// ── Format Summary: sort, filter, build Telegram + Calendar text ─────────────
function formatSummaryNode(col) {
  return {
    id: 'n_format_summary',
    name: 'Format: Corporate Summary',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, 2),
    parameters: {
      jsCode: `const jobs = ($json.jobs || []).map(j => j.json || j);

// Sort by relevance DESC, nulls last
jobs.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));

// Filter: relevance >= 40
const relevant = jobs.filter(j => (j.relevance_score || 0) >= 40);

if (relevant.length === 0) {
  return [{ json: { skip: true, telegram_text: '', calendar_description: '', relevant_count: 0, total: jobs.length } }];
}

const top  = relevant.filter(j => j.relevance_score >= 70);
const rest = relevant.filter(j => j.relevance_score >= 40 && j.relevance_score < 70);

// Telegram message
const lines = ['\\u26A0\\uFE0F <b>[JobRadar Corporate] Neue Stellen</b>', ''];

if (top.length > 0) {
  lines.push('\\uD83D\\uDD25 <b>Top Matches (70+):</b>');
  top.slice(0, 10).forEach(j => {
    lines.push('\\u2022 <b>' + (j.job_title || '?') + '</b> @ ' + (j.company_name || '?') + ' <code>' + (j.relevance_score || '?') + '/100</code>');
    if (j.location) lines.push('  \\uD83D\\uDCCD ' + j.location);
    if (j.source_url) lines.push('  <a href="' + j.source_url + '">Link</a>');
  });
  lines.push('');
}

if (rest.length > 0) {
  lines.push('\\uD83D\\uDCCB <b>Weitere (40-69):</b>');
  rest.slice(0, 15).forEach(j => {
    lines.push('\\u2022 ' + (j.job_title || '?') + ' @ ' + (j.company_name || '?') + ' <code>' + (j.relevance_score || '?') + '/100</code>');
  });
  lines.push('');
}

lines.push('Gesamt: ' + relevant.length + ' relevant von ' + jobs.length + ' gefunden');

// Calendar description (Gmail-style HTML)
const calLines = relevant.slice(0, 30).map(j =>
  '<b>' + (j.company_name || '?') + '</b> \\u2014 ' + (j.job_title || '?') +
  ' (' + (j.relevance_score || '?') + '/100)' +
  (j.location ? ' | ' + j.location : '')
);
const calDesc = calLines.join('<br>');

return [{ json: {
  skip: false,
  telegram_text: lines.join('\\n'),
  calendar_description: calDesc,
  relevant_count: relevant.length,
  total: jobs.length
}}];`
    }
  };
}

// ── IF: has relevant jobs ─────────────────────────────────────────────────────
function ifHasRelevantNode(col) {
  return {
    id: 'n_if_has_relevant',
    name: 'IF: has relevant jobs',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col, 2),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose', version: 2 },
        conditions: [{
          id: 'cond_has_relevant',
          leftValue: '={{ $json.relevant_count }}',
          rightValue: 0,
          operator: { type: 'number', operation: 'gt' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── Telegram: Corporate Summary ───────────────────────────────────────────────
function telegramNode(col) {
  return {
    id: 'n_telegram',
    name: 'Telegram: Corporate Summary',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col),
    parameters: {
      method: 'POST',
      url: '=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage',
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: "={{ JSON.stringify({ chat_id: $env.TELEGRAM_CHAT_ID, parse_mode: 'HTML', text: $json.telegram_text, disable_web_page_preview: true }) }}",
      options: { timeout: 10000 }
    }
  };
}

// ── Google Calendar: List today's events ─────────────────────────────────────
function calendarListTodayNode(col) {
  return {
    id: 'n_cal_list_today',
    name: 'Google Calendar: List Today',
    type: 'n8n-nodes-base.googleCalendar',
    typeVersion: 1.3,
    position: pos(col, 3),
    credentials: { googleCalendarOAuth2Api: { id: 'eLQTxfMJ6kryO1Iy', name: 'Google Calendar' } },
    parameters: {
      operation: 'getAll',
      calendar: { __rl: true, value: 'primary', mode: 'list' },
      returnAll: false,
      limit: 50,
      additionalFields: {
        timeMin: "={{ $now.toISODate() + 'T00:00:00Z' }}",
        timeMax: "={{ $now.toISODate() + 'T23:59:59Z' }}"
      }
    }
  };
}

// ── Find [JobRadar Corporate] event ──────────────────────────────────────────
function findCalendarCorpEventNode(col) {
  return {
    id: 'n_cal_find_corp',
    name: 'Find [JobRadar Corporate] Event',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col, 3),
    parameters: {
      jsCode: `const items = $input.all().map(i => i.json);
const todayEvent = items.find(e => (e.summary || '').includes('[JobRadar Corporate]'));
const summary = $('Format: Corporate Summary').first().json;

return [{ json: {
  event_id:        todayEvent ? todayEvent.id : null,
  event_found:     !!todayEvent,
  new_description: summary.calendar_description,
  event_title:     '[JobRadar Corporate] ' + $now.toISODate(),
  existing_desc:   todayEvent ? (todayEvent.description || '') : ''
}}];`
    }
  };
}

// ── IF: calendar event exists ─────────────────────────────────────────────────
function ifCalendarCorpExistsNode(col) {
  return {
    id: 'n_if_cal_exists',
    name: 'IF: calendar event exists',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col, 3),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose', version: 2 },
        conditions: [{
          id: 'cond_cal_exists',
          leftValue: '={{ $json.event_found }}',
          rightValue: true,
          operator: { type: 'boolean', operation: 'true' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── Google Calendar: Update Corp Event ───────────────────────────────────────
function calendarUpdateCorpNode(col) {
  return {
    id: 'n_cal_update_corp',
    name: 'Google Calendar: Update Corp Event',
    type: 'n8n-nodes-base.googleCalendar',
    typeVersion: 1.3,
    position: pos(col, 2),
    credentials: { googleCalendarOAuth2Api: { id: 'eLQTxfMJ6kryO1Iy', name: 'Google Calendar' } },
    parameters: {
      operation: 'update',
      calendar: { __rl: true, value: 'primary', mode: 'list' },
      eventId: '={{ $json.event_id }}',
      updateFields: {
        description: "={{ $json.existing_desc ? $json.existing_desc + '<br><br>' + $json.new_description : $json.new_description }}"
      }
    }
  };
}

// ── Google Calendar: Create Corp Event ───────────────────────────────────────
function calendarCreateCorpNode(col) {
  return {
    id: 'n_cal_create_corp',
    name: 'Google Calendar: Create Corp Event',
    type: 'n8n-nodes-base.googleCalendar',
    typeVersion: 1.3,
    position: pos(col, 4),
    credentials: { googleCalendarOAuth2Api: { id: 'eLQTxfMJ6kryO1Iy', name: 'Google Calendar' } },
    parameters: {
      operation: 'create',
      calendar: { __rl: true, value: 'primary', mode: 'list' },
      title: "={{ '[JobRadar Corporate] ' + $now.toISODate() }}",
      start: "={{ $now.toISODate() + 'T09:00:00' }}",
      end:   "={{ $now.toISODate() + 'T09:30:00' }}",
      additionalFields: { description: '={{ $json.new_description }}' }
    }
  };
}

// ── IF: priority = high (kept for compatibility, unused) ─────────────────────
function ifPriorityNode(col) {
  return stopNode('n_if_priority_unused', 'Unused: Stop', col, 10);
}

// ══════════════════════════════════════════════════════════════════════════════
// Assemble flow
// ══════════════════════════════════════════════════════════════════════════════

const nodes = [];
const connections = {};

// Trigger
nodes.push(triggerNode);

// Greenhouse nodes
const ghNodes = [];
const ghFlatNodes = [];
GREENHOUSE_COMPANIES.forEach((co, i) => {
  const n = greenhouseNode(co, 1, i - Math.floor(GREENHOUSE_COMPANIES.length / 2));
  const f = greenhouseFlattenNode(co, 2, i - Math.floor(GREENHOUSE_COMPANIES.length / 2));
  nodes.push(n, f);
  ghNodes.push(n);
  ghFlatNodes.push(f);
});

// Lever nodes
const lvNodes = [];
const lvFlatNodes = [];
LEVER_COMPANIES.forEach((co, i) => {
  const offset = GREENHOUSE_COMPANIES.length;
  const n = leverNode(co, 1, i + offset - Math.floor(TOTAL_INPUTS / 2));
  const f = leverFlattenNode(co, 2, i + offset - Math.floor(TOTAL_INPUTS / 2));
  nodes.push(n, f);
  lvNodes.push(n);
  lvFlatNodes.push(f);
});

// Direct HTTP nodes
const httpNodes = [];
const httpFlatNodes = [];
DIRECT_HTTP.forEach((co, i) => {
  const offset = GREENHOUSE_COMPANIES.length + LEVER_COMPANIES.length;
  const n = directHttpNode(co, 1, i + offset - Math.floor(TOTAL_INPUTS / 2));
  const f = directHttpFlattenNode(co, 2, i + offset - Math.floor(TOTAL_INPUTS / 2));
  nodes.push(n, f);
  httpNodes.push(n);
  httpFlatNodes.push(f);
});

// Firecrawl stubs (not connected to merge - just present for documentation)
FIRECRAWL_STUBS.forEach((co, i) => {
  nodes.push(firecrawlStubNode(co, 1, TOTAL_INPUTS + i));
});

// Pipeline nodes
const mergeN         = mergeNode(3);
const kwFilterN      = keywordFilterNode(4);
const normalizeN     = normalizeNode(5);
const dedupN         = dedupNode(6);
const ifDedupN       = ifNotProcessedNode(7);
const llmN           = llmNode(8);
const parseN         = parseNode(9);
const ifRelatedN     = ifJobRelatedNode(10);
const stopNotRelatedN = stopNode('n_stop_not_related', 'Not Job Related: Stop', 11, 1);
const prepareN       = prepareDbNode(11);
const dbWriteN       = dbWriteNode(12);

// Per-job: interview calendar (unchanged)
const ifInterviewN     = ifInterviewDateNode(13);
const calInterviewN    = calendarInterviewNode(14);
const stopNoInterviewN = stopNode('n_stop_no_interview', 'No Interview Date: Stop', 14, -2);

// Aggregated pipeline: Enrich → Aggregate → Format → IF:relevant → Telegram + Calendar
const enrichN        = enrichNode(13);
const aggregateN     = aggregateNode(14);
const formatSummaryN = formatSummaryNode(15);
const ifHasRelevantN = ifHasRelevantNode(16);
const telegramN      = telegramNode(17);
const calListTodayN  = calendarListTodayNode(17);
const findCalCorpN   = findCalendarCorpEventNode(18);
const ifCalExistsN   = ifCalendarCorpExistsNode(19);
const calUpdateCorpN = calendarUpdateCorpNode(20);
const calCreateCorpN = calendarCreateCorpNode(20);

nodes.push(mergeN, kwFilterN, normalizeN, dedupN, ifDedupN, llmN, parseN,
           ifRelatedN, stopNotRelatedN, prepareN, dbWriteN,
           ifInterviewN, calInterviewN, stopNoInterviewN,
           enrichN, aggregateN, formatSummaryN, ifHasRelevantN,
           telegramN, calListTodayN, findCalCorpN, ifCalExistsN,
           calUpdateCorpN, calCreateCorpN);

// ── Build connections ───────────────────────────────────────────────────────

// Trigger → all fetch nodes
connections[triggerNode.name] = {
  main: [[
    ...ghNodes.map(n => ({ node: n.name, type: 'main', index: 0 })),
    ...lvNodes.map(n => ({ node: n.name, type: 'main', index: 0 })),
    ...httpNodes.map(n => ({ node: n.name, type: 'main', index: 0 })),
  ]]
};

// Fetch → Flatten (Greenhouse)
ghNodes.forEach((n, i) => {
  connections[n.name] = { main: [[{ node: ghFlatNodes[i].name, type: 'main', index: 0 }]] };
});
// Fetch → Flatten (Lever)
lvNodes.forEach((n, i) => {
  connections[n.name] = { main: [[{ node: lvFlatNodes[i].name, type: 'main', index: 0 }]] };
});
// Fetch → Flatten (HTTP)
httpNodes.forEach((n, i) => {
  connections[n.name] = { main: [[{ node: httpFlatNodes[i].name, type: 'main', index: 0 }]] };
});

// All Flatten → Merge (each to a different input port)
const allFlatNodes = [...ghFlatNodes, ...lvFlatNodes, ...httpFlatNodes];
allFlatNodes.forEach((n, i) => {
  connections[n.name] = { main: [[{ node: mergeN.name, type: 'main', index: i }]] };
});

// Pipeline connections (up to DB write)
connections[mergeN.name]     = { main: [[{ node: kwFilterN.name,    type: 'main', index: 0 }]] };
connections[kwFilterN.name]  = { main: [[{ node: normalizeN.name,   type: 'main', index: 0 }]] };
connections[normalizeN.name] = { main: [[{ node: dedupN.name,       type: 'main', index: 0 }]] };
connections[dedupN.name]     = { main: [[{ node: ifDedupN.name,     type: 'main', index: 0 }]] };
connections[ifDedupN.name]   = { main: [
  [{ node: llmN.name, type: 'main', index: 0 }],
  []
]};
connections[llmN.name]       = { main: [[{ node: parseN.name,       type: 'main', index: 0 }]] };
connections[parseN.name]     = { main: [[{ node: ifRelatedN.name,   type: 'main', index: 0 }]] };
connections[ifRelatedN.name] = { main: [
  [{ node: prepareN.name,        type: 'main', index: 0 }],
  [{ node: stopNotRelatedN.name, type: 'main', index: 0 }]
]};
connections[prepareN.name]   = { main: [[{ node: dbWriteN.name,     type: 'main', index: 0 }]] };

// DB write → per-job interview branch + aggregated pipeline (fan-out)
connections[dbWriteN.name] = { main: [[
  { node: ifInterviewN.name, type: 'main', index: 0 },
  { node: enrichN.name,      type: 'main', index: 0 }
]]};

// Per-job interview branch
connections[ifInterviewN.name] = { main: [
  [{ node: calInterviewN.name,    type: 'main', index: 0 }],
  [{ node: stopNoInterviewN.name, type: 'main', index: 0 }]
]};

// Aggregated pipeline
connections[enrichN.name]        = { main: [[{ node: aggregateN.name,     type: 'main', index: 0 }]] };
connections[aggregateN.name]     = { main: [[{ node: formatSummaryN.name, type: 'main', index: 0 }]] };
connections[formatSummaryN.name] = { main: [[{ node: ifHasRelevantN.name, type: 'main', index: 0 }]] };

// IF: has relevant → Telegram + Calendar pipeline in parallel; false → stop
connections[ifHasRelevantN.name] = { main: [
  [
    { node: telegramN.name,     type: 'main', index: 0 },
    { node: calListTodayN.name, type: 'main', index: 0 }
  ],
  []  // no relevant jobs: stop
]};

// Calendar pipeline
connections[calListTodayN.name] = { main: [[{ node: findCalCorpN.name,   type: 'main', index: 0 }]] };
connections[findCalCorpN.name]  = { main: [[{ node: ifCalExistsN.name,   type: 'main', index: 0 }]] };
connections[ifCalExistsN.name]  = { main: [
  [{ node: calUpdateCorpN.name, type: 'main', index: 0 }],
  [{ node: calCreateCorpN.name, type: 'main', index: 0 }]
]};

// ── Output ──────────────────────────────────────────────────────────────────
const flow = {
  name: 'JobRadar -- Flow 2b: Corporate Career Pages',
  nodes,
  connections,
  settings: { executionOrder: 'v1' }
};

const json = JSON.stringify(flow, null, 2);
JSON.parse(json); // validate

const outPath = path.join(__dirname, '../n8n/corporate-flow-import.json');
fs.writeFileSync(outPath, json, 'utf8');

console.log('Flow 2b generated successfully');
console.log('Nodes:', nodes.length);
console.log('Sources:', TOTAL_INPUTS, '(Greenhouse:', GREENHOUSE_COMPANIES.length, '| Lever:', LEVER_COMPANIES.length, '| HTTP:', DIRECT_HTTP.length, ')');
console.log('Stubs (not connected):', FIRECRAWL_STUBS.length);
console.log('Output:', outPath);
