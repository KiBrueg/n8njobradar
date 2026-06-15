import json

GEWERBE_CAL_ID = "cdb3fac04c0616e603e1ced86dfe3022950d443273a66812e83b847306508d49@group.calendar.google.com"

FEEDS_CODE = """// RSS feed sources for job + freelance discovery
// job_type: 'employment' = Anstellung | 'freelance' = Gewerbe/Projekt
// Edit ONLY this list to add/remove feeds.

const FEEDS = [
  // ── Employment (Anstellung) ──────────────────────────────────────────────
  { url: 'https://remotive.com/remote-jobs/feed?category=software-dev&search=python',       label: 'remotive-python', job_type: 'employment' },
  { url: 'https://remotive.com/remote-jobs/feed?category=software-dev&search=automation',   label: 'remotive-auto',   job_type: 'employment' },
  { url: 'https://berlinstartupjobs.com/feed/',                                             label: 'berlin-startup',  job_type: 'employment' },
  { url: 'https://www.arbeitnow.com/feed',                                                  label: 'arbeitnow',       job_type: 'employment' },
  { url: 'https://jobicy.com/?feed=job_feed&job_categories=backend&job_types=full-time,contract&search_region=europe', label: 'jobicy-eu', job_type: 'employment' },
  // ── Freelance / Contract (Gewerbe) ───────────────────────────────────────
  { url: 'https://remoteok.com/remote-dev-jobs.rss',   label: 'remoteok-dev',   job_type: 'freelance' },
  { url: 'https://weworkremotely.com/remote-jobs.rss', label: 'weworkremotely', job_type: 'freelance' },
];

return FEEDS.map(f => ({ json: f }));"""

PARSE_RSS_CODE = r"""// Parse raw RSS 2.0 / Atom XML into individual job items.
// Handles <item> (RSS 2.0) and <entry> (Atom).
// Carries label + job_type from RSS Feed List node.

const feedConfig = $('RSS Feed List').item.json;
const raw = $input.item.json;
const xmlText = (typeof raw.data === 'string') ? raw.data : '';

if (!xmlText) {
  console.log('RSS: empty response from', feedConfig.label);
  return [];
}

function getTag(block, tag) {
  const re = new RegExp('<' + tag + '[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?<\\/' + tag + '>', 'i');
  const m = block.match(re);
  return m ? m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : null;
}

const blocks = [];
let m;
const rssRe  = /<item>([\s\S]*?)<\/item>/gi;
const atomRe = /<entry>([\s\S]*?)<\/entry>/gi;
while ((m = rssRe.exec(xmlText))  !== null) blocks.push(m[1]);
while ((m = atomRe.exec(xmlText)) !== null) blocks.push(m[1]);

if (blocks.length === 0) {
  console.log('RSS: 0 items parsed from', feedConfig.label, xmlText.substring(0, 200));
  return [];
}

// Keep only items from last 72 h
const cutoff = new Date(Date.now() - 72 * 60 * 60 * 1000);

const items = blocks.map(block => ({
  title:       getTag(block, 'title'),
  link:        getTag(block, 'link') || getTag(block, 'guid') || getTag(block, 'id'),
  description: (getTag(block, 'description') || getTag(block, 'content:encoded') || getTag(block, 'summary') || getTag(block, 'content') || '').substring(0, 3000),
  pubDate:     getTag(block, 'pubDate') || getTag(block, 'updated') || getTag(block, 'dc:date'),
})).filter(i => {
  if (!i.link || !i.title) return false;
  if (!i.pubDate) return true;
  const d = new Date(i.pubDate);
  return isNaN(d.getTime()) || d >= cutoff;
});

return items.map(i => ({ json: {
  title:       i.title,
  link:        i.link,
  description: i.description,
  pubDate:     i.pubDate,
  label:       feedConfig.label,
  job_type:    feedConfig.job_type,
  feed_url:    feedConfig.url,
}}));"""

KEYWORD_FILTER_CODE = r"""// Pre-LLM keyword filter — saves ~80% of API costs.
// Drops items with no mention of Python / n8n / AI / Automation.
const INCLUDE = /python|\bn8n\b|\bai\b|llm|gpt|claude|automati|fastapi|docker|machine.?learning|\bml\b|data.?engi|workflow|langchain|openai|anthropic|ki-|künstliche/i;

const item = $input.item.json;
const text = (item.title || '') + ' ' + (item.description || '');

if (!INCLUDE.test(text)) return [];
return [$input.item];"""

NORMALIZE_CODE = r"""// Normalize RSS item → JobRadar standard normalized_input.
const item = $input.item.json;
const isFreelance = (item.job_type === 'freelance');

const rawText = ((item.title || '') + '\n\n' + (item.description || '')).substring(0, 8000);

return [{ json: {
  normalized_input: {
    input_source:     'scraped',
    source_detail:    'rss',
    job_type:         item.job_type || 'employment',
    email_account_id: null,
    email_address:    null,
    email_provider:   null,
    subject:          item.title,
    date:             item.pubDate || null,
    raw_text:         rawText,
    raw_meta: {
      url:      item.link,
      label:    item.label,
      platform: item.label,
      feed_url: item.feed_url,
    },
    filter_context: isFreelance
      ? 'GEWERBE FILTER: Set is_job_related=FALSE unless project requires Python, n8n, AI, LLM, FastAPI, Docker, or Automation. EXCLUDE SAP, Golang, Java, Payroll, HR. Priority: Python+n8n+AI=high, Python+automation=medium.'
      : 'JOBS FILTER: Set is_job_related=TRUE for Python/AI/automation/data engineering roles. EXCLUDE pure management, PHP-only, Ruby-only. Priority by tech stack match.',
  }
}}];"""

SECURITY_CODE = """const ni = $('Normalize Item').item.json.normalized_input;
return [{ json: { normalized_input: ni, hard_injection_detected: 'no' } }];"""

PARSE_LLM_CODE = r"""const body = $input.item.json;
let jobEvent;
try {
  let raw = (body.choices[0].message.content || '').trim();
  raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  raw = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
  jobEvent = JSON.parse(raw);
} catch (err) {
  throw new Error('LLM invalid JSON: ' + String(body?.choices?.[0]?.message?.content || '').substring(0, 300));
}
if (typeof jobEvent.is_job_related !== 'boolean') throw new Error('is_job_related must be boolean');
if (typeof jobEvent.injection_suspected !== 'boolean') jobEvent.injection_suspected = false;
const ALLOWED = ['create_job','update_stage','add_interview','add_deadline','log_only','flag_error','ignore'];
if (!ALLOWED.includes(jobEvent.action)) throw new Error('invalid action: ' + jobEvent.action);
if (jobEvent.company_id && !/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(jobEvent.company_id))
  jobEvent.company_id = jobEvent.company_id.toLowerCase().replace(/[^a-z0-9-]/g,'-').replace(/--+/g,'-').replace(/^-|-$/g,'');
if (!Array.isArray(jobEvent.tech_stack))       jobEvent.tech_stack = [];
if (!Array.isArray(jobEvent.key_requirements)) jobEvent.key_requirements = [];
const JRC = ['job_posting','hr_invite','interview_invite','test_task','offer','rejection','follow_up','platform_notification','manual_note'];
if (JRC.includes(jobEvent.category)) jobEvent.is_job_related = true;
jobEvent.is_job_related_str = jobEvent.is_job_related ? 'yes' : 'no';
return [{ json: { job_event: jobEvent } }];"""

FILTER_EXPIRED_CODE = r"""const e = $('Parse LLM Response').item.json.job_event;
const deadline = e.application_deadline || e.response_deadline || null;
if (deadline) {
  const d = new Date(deadline);
  if (!isNaN(d.getTime()) && d < new Date()) return [];
}
return [$input.item];"""

PREPARE_DB_CODE = r"""const e  = $input.item.json.job_event;
const ni = $('Normalize Item').item.json.normalized_input;
const rawText   = ni.raw_text;
const sourceUrl = (ni.raw_meta && ni.raw_meta.url) || null;

function sql(v)  { if (v==null) return 'NULL'; return "'"+String(v).replace(/'/g,"''")+"'"; }
function num(v)  { if (v==null) return 'NULL'; const n=parseFloat(v); return isNaN(n)?'NULL':String(n); }
function bool(v) { return v===true?'TRUE':'FALSE'; }
function dt(v)   { return v?"'"+String(v).replace(/'/g,"''")+"'":'NULL'; }
function en(v,t) { return v?"'"+String(v).replace(/'/g,"''")+"'::"+t:'NULL'; }
function arr(vals) {
  if (!vals||vals.length===0) return "'{}'";
  return "'{"+vals.map(v=>'"'+String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"').join(',')+"}'"; }
function jsonb(v) {
  if (!v) return "'{}'::jsonb";
  return "'"+JSON.stringify(v).replace(/'/g,"''")+"'::jsonb"; }
function normWM(v) {
  if (!v) return null;
  const s=String(v).toLowerCase().replace(/[-\s]/g,'_');
  return {on_site:'onsite',onsite:'onsite',in_office:'onsite',office:'onsite',vor_ort:'onsite',
    full_remote:'remote',fully_remote:'remote',remote:'remote',homeoffice:'remote',
    hybrid:'hybrid',partially_remote:'hybrid'}[s]||null; }
function normSen(v) {
  if (!v) return null;
  const s=String(v).toLowerCase().replace(/[-\s]/g,'_');
  return {intern:'intern',junior:'junior',jr:'junior',middle:'middle',mid:'middle',
    medior:'middle',intermediate:'middle',senior:'senior',sr:'senior',
    lead:'lead',tech_lead:'lead',principal:'principal',staff:'principal'}[s]||null; }

return [{json:{job_event:e,db:{
  company_id_sql:           sql(e.company_id||'unknown'),
  company_name_sql:         sql(e.company_name||'Unknown Company'),
  employer_id_sql:          sql(e.employer_id),
  employer_name_sql:        sql(e.employer_name),
  job_id_fuzzy_sql:         sql(e.job_id_fuzzy||'unknown__unknown__unknown'),
  job_title_sql:            sql(e.job_title),
  location_sql:             sql(e.location),
  job_thread_key_sql:       sql(e.job_thread_key),
  seniority_sql:            en(normSen(e.seniority),'seniority_enum'),
  work_mode_sql:            en(normWM(e.work_mode),'work_mode_enum'),
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
  source_url_sql:           sql(sourceUrl||e.source_url),
  source_input_sql:         en('scraped','input_source_enum'),
  job_type_sql:             sql(ni.job_type||'employment'),
  summary_sql:              sql(e.summary),
  category_sql:             en(e.category,'job_category_enum'),
  action_sql:               sql(e.action),
  is_job_related_sql:       bool(e.is_job_related),
  call_platform_sql:        en(e.call_platform,'call_platform_enum'),
  call_platform_raw_sql:    sql(e.call_platform_raw),
  raw_text_sql:             sql(rawText),
  parsed_json_sql:          jsonb(e),
  sender_risk_level_sql:    sql('unknown'),
  sender_risk_signals_sql:  arr([]),
}}}];"""

CAL_PREP_CODE = r"""const e  = $('Parse LLM Response').item.json.job_event;
const ni = $('Normalize Item').item.json.normalized_input;
const db = $input.item.json;
const rel = parseInt(e.relevance_score || 0);
const isFreelance = (ni.job_type === 'freelance');
const colorId = rel >= 80 ? '2' : rel >= 50 ? '5' : '8';
const icon = isFreelance ? '🔧' : '💼'; // 🔧 or 💼

let rateStr = '';
if (e.salary_min) {
  const p = {hourly:'/h',daily:'/d',monthly:'/mo'}[e.salary_period]||'';
  rateStr = ' | '+(e.salary_min)+(e.salary_max?'–'+e.salary_max:'')+(e.salary_currency||'EUR')+p;
}
const calSummary = icon+' [RSS] '+(e.job_title||'Job')+' @ '+(e.company_name||'?')+rateStr;
const todayISO = new Date().toISOString().split('T')[0];
const calStart = ((e.application_deadline||e.response_deadline||todayISO)+'').substring(0,10);
const sourceUrl = (ni.raw_meta&&ni.raw_meta.url)||'';
const platform  = (ni.raw_meta&&(ni.raw_meta.platform||ni.raw_meta.label))||'?';
const today = new Date().toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',year:'numeric'});
const tech = Array.isArray(e.tech_stack)&&e.tech_stack.length ? e.tech_stack.slice(0,8).join(' · ') : null;
const bar = '█'.repeat(Math.round(rel/10))+'░'.repeat(10-Math.round(rel/10));

const lines = ['═'.repeat(30), icon+' RSS '+(isFreelance?'GEWERBE':'JOBS')+'-RADAR', '═'.repeat(30), '',
  '🟢 '+(e.company_name||'?')];
if (tech) lines.push('🔧 Stack: '+tech);
if (e.location) lines.push('📍 '+(e.location)+(e.work_mode?' | '+e.work_mode:''));
if (e.salary_min) lines.push('💰 '+(e.salary_min)+(e.salary_max?'–'+e.salary_max:'')+' '+(e.salary_currency||'EUR'));
lines.push('', '📈 Relevanz: ['+bar+'] '+rel+'/100', '');
if (e.summary) { lines.push('💬 '+e.summary, ''); }
lines.push('─'.repeat(30));
if (sourceUrl) lines.push('🔗 '+sourceUrl);
lines.push('🏷️ '+platform+' | 📅 '+today, '', 'JobRadar RSS — KI Automation Intelligence Hub');

return [{json:{job_id:db.job_id, stage:db.stage, priority:db.priority, summary:db.summary,
  job_type:ni.job_type, calSummary, calStart, calEnd:calStart, calColorId:colorId,
  calDescription:lines.join('\n')}}];"""

DB_SQL = """WITH
co AS (
  INSERT INTO companies (company_id, name, meta)
  VALUES ({{ $json.db.company_id_sql }}, {{ $json.db.company_name_sql }}, '{}')
  ON CONFLICT (tenant_id, company_id) DO UPDATE SET updated_at = NOW()
  RETURNING id
),
em AS (
  INSERT INTO employers (employer_id, company_id, name)
  SELECT {{ $json.db.employer_id_sql }}, {{ $json.db.company_id_sql }}, {{ $json.db.employer_name_sql }}
  WHERE  {{ $json.db.employer_id_sql }} IS NOT NULL
  ON CONFLICT (tenant_id, employer_id) DO UPDATE SET
    name = COALESCE(EXCLUDED.name, employers.name), updated_at = NOW()
  RETURNING id
),
j AS (
  INSERT INTO jobs (
    job_id_fuzzy, company_id, employer_id, job_title, location, seniority,
    work_mode, work_mode_raw, working_hours,
    salary_currency, salary_min, salary_max, salary_period,
    tech_stack, key_requirements,
    current_stage, priority, priority_level,
    interview_date, response_deadline, application_deadline,
    has_had_call, call_count, last_call_date,
    source_url, source_input, summary, job_type
  ) VALUES (
    {{ $json.db.job_id_fuzzy_sql }}, {{ $json.db.company_id_sql }}, {{ $json.db.employer_id_sql }},
    {{ $json.db.job_title_sql }}, {{ $json.db.location_sql }}, {{ $json.db.seniority_sql }},
    {{ $json.db.work_mode_sql }}, {{ $json.db.work_mode_raw_sql }}, {{ $json.db.working_hours_sql }},
    {{ $json.db.salary_currency_sql }}, {{ $json.db.salary_min_sql }}, {{ $json.db.salary_max_sql }}, {{ $json.db.salary_period_sql }},
    {{ $json.db.tech_stack_sql }}, {{ $json.db.key_requirements_sql }},
    {{ $json.db.current_stage_sql }}, {{ $json.db.priority_sql }}, {{ $json.db.priority_level_sql }},
    {{ $json.db.interview_date_sql }}, {{ $json.db.response_deadline_sql }}, {{ $json.db.application_deadline_sql }},
    {{ $json.db.has_had_call_sql }}, {{ $json.db.call_count_sql }}, {{ $json.db.last_call_date_sql }},
    {{ $json.db.source_url_sql }}, {{ $json.db.source_input_sql }}, {{ $json.db.summary_sql }}, {{ $json.db.job_type_sql }}
  )
  ON CONFLICT (tenant_id, job_id_fuzzy) DO UPDATE SET
    current_stage = EXCLUDED.current_stage, priority = EXCLUDED.priority, priority_level = EXCLUDED.priority_level,
    interview_date = COALESCE(EXCLUDED.interview_date, jobs.interview_date),
    response_deadline = COALESCE(EXCLUDED.response_deadline, jobs.response_deadline),
    application_deadline = COALESCE(EXCLUDED.application_deadline, jobs.application_deadline),
    tech_stack = CASE WHEN array_length(EXCLUDED.tech_stack,1)>0 THEN EXCLUDED.tech_stack ELSE jobs.tech_stack END,
    source_url = COALESCE(EXCLUDED.source_url, jobs.source_url),
    summary = EXCLUDED.summary, job_type = EXCLUDED.job_type, updated_at = NOW()
  RETURNING id, job_id_fuzzy, current_stage::text, priority::text, summary, interview_date
),
ev AS (
  INSERT INTO job_events (
    job_id, job_thread_key, job_id_fuzzy, input_source, source_detail,
    category, is_job_related, action, stage, priority, priority_level,
    interview_date, response_deadline, application_deadline,
    call_platform, call_platform_raw, raw_text, parsed_json,
    sender_risk_level, sender_risk_signals
  )
  SELECT (SELECT id FROM j), {{ $json.db.job_thread_key_sql }}, {{ $json.db.job_id_fuzzy_sql }},
    {{ $json.db.source_input_sql }}, 'rss',
    {{ $json.db.category_sql }}, {{ $json.db.is_job_related_sql }}, {{ $json.db.action_sql }},
    {{ $json.db.current_stage_sql }}, {{ $json.db.priority_sql }}, {{ $json.db.priority_level_sql }},
    {{ $json.db.interview_date_sql }}, {{ $json.db.response_deadline_sql }}, {{ $json.db.application_deadline_sql }},
    {{ $json.db.call_platform_sql }}, {{ $json.db.call_platform_raw_sql }},
    {{ $json.db.raw_text_sql }}, {{ $json.db.parsed_json_sql }},
    {{ $json.db.sender_risk_level_sql }}, {{ $json.db.sender_risk_signals_sql }}
  RETURNING id
)
SELECT (SELECT id FROM j) AS job_id, (SELECT job_id_fuzzy FROM j) AS job_id_fuzzy,
       (SELECT current_stage FROM j) AS stage, (SELECT priority FROM j) AS priority,
       (SELECT summary FROM j) AS summary, (SELECT interview_date FROM j) AS interview_date,
       (SELECT id FROM ev) AS event_id;"""

TELEGRAM_BODY = r"""={{ JSON.stringify({
  chat_id: parseInt($env.TELEGRAM_GEWERBE_CHAT_ID),
  parse_mode: 'HTML',
  text: [
    ($json.job_type==='freelance' ? '🔧' : '💼')
      + ' <b>[RSS] ' + ($('Parse LLM Response').item.json.job_event.company_name || '?') + '</b>',
    ($('Parse LLM Response').item.json.job_event.job_title || '—'),
    '',
    'Stage: <code>' + ($json.stage||'discovered') + '</code>  Priority: <b>' + ($json.priority||'?') + '</b>',
    'Feed: ' + ((($('Normalize Item').item.json.normalized_input.raw_meta)||{}).label||'?'),
    '',
    ($json.summary || '')
  ].join('\n'),
  disable_web_page_preview: true
}) }}"""

nodes = [
    {
        "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 6, "triggerAtHour": 7, "triggerAtMinute": 0}]}},
        "id": "n_sched", "name": "Schedule: Every 6h",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.1, "position": [200, 340],
        "notes": "Every 6h at 07:00/13:00/19:00/01:00.\nFetches 7 RSS feeds, ~80% filtered before LLM."
    },
    {
        "parameters": {}, "id": "n_manual", "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [200, 180]
    },
    {
        "parameters": {"jsCode": FEEDS_CODE},
        "id": "n_feeds", "name": "RSS Feed List",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [420, 300],
        "notes": "Add/remove feeds here only.\n5 employment + 2 freelance sources.\nSupports RSS 2.0 and Atom."
    },
    {
        "parameters": {
            "method": "GET", "url": "={{ $json.url }}",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Accept", "value": "application/rss+xml, application/xml, text/xml, */*"},
                {"name": "User-Agent", "value": "Mozilla/5.0 (compatible; JobRadar-RSS/1.0)"}
            ]},
            "options": {"response": {"response": {"responseFormat": "text"}}, "timeout": 20000}
        },
        "id": "n_fetch", "name": "HTTP: Fetch RSS Feed",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [640, 300],
        "notes": "Direct HTTP — no API key, no cost.\nUser-Agent prevents 403 on some feeds."
    },
    {
        "parameters": {
            "conditions": {"conditions": [{"id": "cond_ok", "leftValue": "={{ $json.data }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty"}}], "combinator": "and"},
            "options": {}
        },
        "id": "n_if_ok", "name": "IF: fetch ok",
        "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [860, 300]
    },
    {
        "parameters": {"jsCode": PARSE_RSS_CODE},
        "id": "n_parse_rss", "name": "Parse RSS Items",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1080, 300],
        "notes": "Splits XML into individual items.\nFilters items older than 72h.\nOutputs: title, link, description, pubDate, label, job_type."
    },
    {
        "parameters": {"jsCode": KEYWORD_FILTER_CODE},
        "id": "n_kw_filter", "name": "Keyword Filter",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1300, 300],
        "notes": "Drops items without Python/AI/n8n keywords.\nSaves ~80% of LLM API calls."
    },
    {
        "parameters": {"jsCode": NORMALIZE_CODE},
        "id": "n_normalize", "name": "Normalize Item",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1520, 300],
        "notes": "Builds normalized_input.\nAdds filter_context based on job_type."
    },
    {
        "parameters": {"jsCode": SECURITY_CODE},
        "id": "n_security", "name": "Skip Security Checks",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1740, 300],
        "notes": "Trusted RSS sources. No domain to verify."
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"},
                {"name": "content-type", "value": "application/json"}
            ]},
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({ model: 'qwen/qwen3-30b-a3b-instruct-2507', max_tokens: 2048, messages: [{ role: 'system', content: $env.JOBRADAR_SYSTEM_PROMPT }, { role: 'user', content: JSON.stringify($json.normalized_input) }] }) }}",
            "options": {"timeout": 60000}
        },
        "id": "n_llm", "name": "LLM Call (OpenRouter)",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1960, 300]
    },
    {
        "parameters": {"jsCode": PARSE_LLM_CODE},
        "id": "n_parse_llm", "name": "Parse LLM Response",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2180, 300]
    },
    {
        "parameters": {
            "conditions": {"conditions": [{"id": "cond_rel", "leftValue": "={{ $json.job_event.is_job_related_str }}", "rightValue": "yes", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
            "options": {}
        },
        "id": "n_if_related", "name": "IF: is_job_related",
        "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [2400, 300]
    },
    {
        "parameters": {"jsCode": FILTER_EXPIRED_CODE},
        "id": "n_filter_exp", "name": "Filter: Skip Expired",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2620, 300]
    },
    {
        "parameters": {"jsCode": PREPARE_DB_CODE},
        "id": "n_prepare", "name": "Prepare DB Params",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [2840, 300]
    },
    {
        "parameters": {
            "operation": "executeQuery",
            "query": DB_SQL,
            "options": {}
        },
        "id": "n_db_write", "name": "DB: Write All",
        "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [3060, 300],
        "credentials": {"postgres": {"id": "Tvuhat51UDCzKwnE", "name": "Postgres account"}},
        "notes": "Idempotent upsert on job_id_fuzzy.\nsource_detail='rss' in job_events for audit."
    },
    {
        "parameters": {"jsCode": CAL_PREP_CODE},
        "id": "n_cal_prep", "name": "Prepare Calendar Data",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [3280, 300],
        "notes": "💼 = employment (Anstellung), 🔧 = freelance.\nColor: green>=80, yellow>=50, grey<50."
    },
    {
        "parameters": {
            "resource": "event", "operation": "create",
            "calendar": {"__rl": True, "value": GEWERBE_CAL_ID, "mode": "id"},
            "start": "={{ $json.calStart }}", "end": "={{ $json.calEnd }}",
            "additionalFields": {
                "summary": "={{ $json.calSummary }}",
                "description": "={{ $json.calDescription }}",
                "colorId": "={{ $json.calColorId }}",
                "allday": True
            }
        },
        "id": "n_calendar", "name": "Calendar: RSS Event",
        "type": "n8n-nodes-base.googleCalendar", "typeVersion": 1.2, "position": [3500, 300],
        "credentials": {"googleCalendarOAuth2Api": {"id": "eLQTxfMJ6kryO1Iy", "name": "Google Calendar account"}},
        "notes": "Writes to JobRadar Gewerbe calendar (both employment and freelance).\nTODO: add JOBRADAR_MAIN_CALENDAR_ID env var for employment if needed."
    },
    {
        "parameters": {
            "method": "POST",
            "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
            "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": TELEGRAM_BODY,
            "options": {"timeout": 10000}
        },
        "id": "n_telegram", "name": "Telegram: RSS Alert",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [3720, 300],
        "notes": "Sends to TELEGRAM_GEWERBE_CHAT_ID.\n💼 icon = employment job, 🔧 = freelance project."
    },
]

connections = {
    "Schedule: Every 6h": {"main": [[{"node": "RSS Feed List", "type": "main", "index": 0}]]},
    "Manual Trigger":     {"main": [[{"node": "RSS Feed List", "type": "main", "index": 0}]]},
    "RSS Feed List":      {"main": [[{"node": "HTTP: Fetch RSS Feed", "type": "main", "index": 0}]]},
    "HTTP: Fetch RSS Feed": {"main": [[{"node": "IF: fetch ok", "type": "main", "index": 0}]]},
    "IF: fetch ok": {"main": [
        [{"node": "Parse RSS Items", "type": "main", "index": 0}],
        []
    ]},
    "Parse RSS Items":       {"main": [[{"node": "Keyword Filter", "type": "main", "index": 0}]]},
    "Keyword Filter":        {"main": [[{"node": "Normalize Item", "type": "main", "index": 0}]]},
    "Normalize Item":        {"main": [[{"node": "Skip Security Checks", "type": "main", "index": 0}]]},
    "Skip Security Checks":  {"main": [[{"node": "LLM Call (OpenRouter)", "type": "main", "index": 0}]]},
    "LLM Call (OpenRouter)": {"main": [[{"node": "Parse LLM Response", "type": "main", "index": 0}]]},
    "Parse LLM Response":    {"main": [[{"node": "IF: is_job_related", "type": "main", "index": 0}]]},
    "IF: is_job_related": {"main": [
        [{"node": "Filter: Skip Expired", "type": "main", "index": 0}],
        []
    ]},
    "Filter: Skip Expired": {"main": [[{"node": "Prepare DB Params", "type": "main", "index": 0}]]},
    "Prepare DB Params":    {"main": [[{"node": "DB: Write All", "type": "main", "index": 0}]]},
    "DB: Write All":        {"main": [[{"node": "Prepare Calendar Data", "type": "main", "index": 0}]]},
    "Prepare Calendar Data": {"main": [[{"node": "Calendar: RSS Event", "type": "main", "index": 0}]]},
    "Calendar: RSS Event":   {"main": [[{"node": "Telegram: RSS Alert", "type": "main", "index": 0}]]},
}

flow = {
    "name": "JobRadar -- Flow 10: RSS Job Feed",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"}
}

out = "n8n/rss-flow-api.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(flow, f, ensure_ascii=False, indent=2)

print(f"Written {out}: {len(nodes)} nodes, {len(connections)} connections")
