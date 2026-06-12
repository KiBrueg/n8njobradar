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
];

// ── Lever companies ─────────────────────────────────────────────────────────
const LEVER_COMPANIES = [
  { slug: 'aleph-alpha',  label: 'Aleph Alpha',     note: 'AI Research, Heidelberg' },
];

// ── Direct HTTP (JSON APIs) ─────────────────────────────────────────────────
const DIRECT_HTTP = [
  {
    id: 'zalando',
    label: 'Zalando',
    url: 'https://jobs.zalando.com/api/jobs/?limit=100&offset=0',
    note: 'Berlin, Tech/Platform',
    source_detail: 'zalando_api'
  },
];

// ── Firecrawl stubs (activate later) ───────────────────────────────────────
const FIRECRAWL_STUBS = [
  { id: 'sap',          label: 'SAP Jobs',          note: 'Activate: jobs.sap.com/search/?q=automation+engineer' },
  { id: 'siemens',      label: 'Siemens Jobs',      note: 'Activate: jobs.siemens.com/?keywords=automation' },
  { id: 'deliveryhero', label: 'Delivery Hero Jobs', note: 'Activate: careers.deliveryhero.com (custom ATS)' },
  { id: 'teamviewer',   label: 'TeamViewer Jobs',   note: 'Activate: teamviewer.com/en/company/careers (custom ATS)' },
];

// ── Keyword filter (applied before LLM to save tokens) ─────────────────────
const KEYWORDS = [
  'automation', 'engineer', 'developer', 'devops', 'platform',
  'workflow', 'integration', 'python', 'machine learning', 'ai ',
  'n8n', 'data engineer', 'backend', 'software', 'cloud', 'infrastructure'
];

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
    onError: 'continueRegularOutput',
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
      jsCode: `const resp = $input.item.json;
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
    onError: 'continueRegularOutput',
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
      jsCode: `const jobs = Array.isArray($input.item.json) ? $input.item.json : [];
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
    onError: 'continueRegularOutput',
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
  return {
    id: 'n_kw_filter',
    name: 'Keyword Filter',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: pos(col),
    notes: 'Filters irrelevant jobs before LLM call to save tokens.',
    parameters: {
      jsCode: `const KEYWORDS = [${kwList}];
const job = $input.item.json;
const text = [(job.title || ''), (job.departments || ''), (job.content || '')].join(' ').toLowerCase();
const match = KEYWORDS.some(kw => text.includes(kw));
if (!match) return [];
return [{ json: job }];`,
      mode: 'runOnceForEachItem'
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
      jsCode: `const j = $input.item.json;
const now = new Date().toISOString();

return [{ json: {
  normalized_input: {
    input_source: 'scraped',
    source_detail: j._source || 'corporate_api',
    email_account_id: null,
    email_address: null,
    email_provider: null,
    subject: j.title || null,
    date: now,
    raw_text: [
      'Title: ' + (j.title || ''),
      'Company: ' + (j._company || ''),
      'Location: ' + (j.location || ''),
      'Department: ' + (j.departments || ''),
      '',
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
} }];`,
      mode: 'runOnceForEachItem'
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
      query: `SELECT je.job_id_fuzzy, j.updated_at
FROM job_events je
JOIN jobs j ON j.job_id_fuzzy = je.job_id_fuzzy
WHERE je.job_id_fuzzy = {{ $json.normalized_input.raw_meta.job_url
  ? "'" + $json.normalized_input.raw_meta.job_url.replace(/'/g,"''").substring(0,200) + "'"
  : "'__no_url__'" }}
  AND j.updated_at > NOW() - INTERVAL '7 days'
LIMIT 1;`,
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
          leftValue: '={{ $json.length }}',
          rightValue: 0,
          operator: { type: 'number', operation: 'equals' }
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
      body: "={{ JSON.stringify({ model: 'qwen/qwen3-30b-a3b-instruct-2507', max_tokens: 2048, messages: [{ role: 'system', content: $env.JOBRADAR_SYSTEM_PROMPT }, { role: 'user', content: JSON.stringify($json.normalized_input) }] }) }}",
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
      jsCode: `const e = $input.item.json.job_event;
const ni = $('Normalize: Corporate Job').item.json.normalized_input;

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

return [{ json: {
  job_event: e,
  db: {
    company_id_sql:           sql(e.company_id||'unknown'),
    company_name_sql:         sql(e.company_name||ni.raw_meta.company||'Unknown Company'),
    employer_id_sql:          sql(e.employer_id),
    employer_name_sql:        sql(e.employer_name),
    job_id_fuzzy_sql:         sql(e.job_id_fuzzy||'unknown__unknown__unknown'),
    job_title_sql:            sql(e.job_title),
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
    source_url_sql:           sql(ni.raw_meta.job_url||e.source_url),
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

// ── IF: priority = high ─────────────────────────────────────────────────────
function ifPriorityNode(col) {
  return {
    id: 'n_if_priority',
    name: 'IF: priority = high',
    type: 'n8n-nodes-base.if',
    typeVersion: 2.2,
    position: pos(col),
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
        conditions: [{
          id: 'cond_priority',
          leftValue: '={{ $json.priority }}',
          rightValue: 'high',
          operator: { type: 'string', operation: 'equals' }
        }],
        combinator: 'and'
      },
      options: {}
    }
  };
}

// ── Telegram alert ──────────────────────────────────────────────────────────
function telegramNode(col) {
  return {
    id: 'n_telegram',
    name: 'Telegram: Job Alert',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: pos(col),
    parameters: {
      method: 'POST',
      url: '=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage',
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: "={{ JSON.stringify({ chat_id: $env.TELEGRAM_CHAT_ID, parse_mode: 'HTML', text: ['\\u{1F3E2} <b>[JobRadar Corporate] ' + ($('Parse LLM Response').item.json.job_event.company_name || 'Unknown') + '</b>', '<b>' + ($('Parse LLM Response').item.json.job_event.job_title || '') + '</b>', '', 'Phase: <code>' + ($json.stage || '') + '</code>  Prioritaet: <b>' + ($json.priority || '') + '</b>', '', ($json.summary || '')].filter(Boolean).join('\\n') }) }}",
      options: { timeout: 10000 }
    }
  };
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
const mergeN = mergeNode(3);
const kwFilterN = keywordFilterNode(4);
const normalizeN = normalizeNode(5);
const dedupN = dedupNode(6);
const ifDedupN = ifNotProcessedNode(7);
const llmN = llmNode(8);
const parseN = parseNode(9);
const ifRelatedN = ifJobRelatedNode(10);
const stopNotRelatedN = stopNode('n_stop_not_related', 'Not Job Related: Stop', 11, 1);
const prepareN = prepareDbNode(11);
const dbWriteN = dbWriteNode(12);
const ifPriorityN = ifPriorityNode(13);
const telegramN = telegramNode(14);
const stopLowPriorityN = stopNode('n_stop_low', 'Low Priority: Stop', 14, 1);

nodes.push(mergeN, kwFilterN, normalizeN, dedupN, ifDedupN, llmN, parseN,
           ifRelatedN, stopNotRelatedN, prepareN, dbWriteN, ifPriorityN, telegramN, stopLowPriorityN);

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

// Pipeline connections
connections[mergeN.name]     = { main: [[{ node: kwFilterN.name,     type: 'main', index: 0 }]] };
connections[kwFilterN.name]  = { main: [[{ node: normalizeN.name,    type: 'main', index: 0 }]] };
connections[normalizeN.name] = { main: [[{ node: dedupN.name,        type: 'main', index: 0 }]] };
connections[dedupN.name]     = { main: [[{ node: ifDedupN.name,      type: 'main', index: 0 }]] };
connections[ifDedupN.name]   = { main: [
  [{ node: llmN.name, type: 'main', index: 0 }],
  []
]};
connections[llmN.name]       = { main: [[{ node: parseN.name,        type: 'main', index: 0 }]] };
connections[parseN.name]     = { main: [[{ node: ifRelatedN.name,    type: 'main', index: 0 }]] };
connections[ifRelatedN.name] = { main: [
  [{ node: prepareN.name,         type: 'main', index: 0 }],
  [{ node: stopNotRelatedN.name,  type: 'main', index: 0 }]
]};
connections[prepareN.name]   = { main: [[{ node: dbWriteN.name,      type: 'main', index: 0 }]] };
connections[dbWriteN.name]   = { main: [[{ node: ifPriorityN.name,   type: 'main', index: 0 }]] };
connections[ifPriorityN.name] = { main: [
  [{ node: telegramN.name,        type: 'main', index: 0 }],
  [{ node: stopLowPriorityN.name, type: 'main', index: 0 }]
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
