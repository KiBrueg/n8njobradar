const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '../n8n/manual-flow-api.json');
const dst = path.join(__dirname, '../n8n/manual-flow-import.json');

// Strip BOM if present
let raw = fs.readFileSync(src, 'utf8');
if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1);

const f = JSON.parse(raw);

// Keep only allowed top-level fields
const clean = {
  name: f.name.replace(/—/g, '--'),
  nodes: f.nodes,
  connections: f.connections,
  settings: f.settings
};

// Process nodes
clean.nodes = clean.nodes.map(node => {
  const n = JSON.parse(JSON.stringify(node));

  // Strip Cyrillic comment lines from jsCode
  if (n.parameters && n.parameters.jsCode) {
    n.parameters.jsCode = n.parameters.jsCode
      .split('\n')
      .filter(line => !/[Ѐ-ӿ]/.test(line))
      .join('\n');
  }

  // Remove empty credential IDs
  if (n.credentials) {
    Object.keys(n.credentials).forEach(key => {
      if (n.credentials[key] && n.credentials[key].id === '') {
        delete n.credentials[key];
      }
    });
    if (Object.keys(n.credentials).length === 0) delete n.credentials;
  }

  // Rename DeepSeek -> OpenRouter node names
  if (n.name === 'DeepSeek API') n.name = 'LLM Call (OpenRouter)';
  if (n.name === 'Parse DeepSeek Response') n.name = 'Parse LLM Response';

  // Replace TODO: Google Calendar NoOp with real node
  if (n.id === 'n_calendar_todo') {
    n.name = 'Google Calendar: Create Event';
    n.type = 'n8n-nodes-base.httpRequest';
    n.typeVersion = 4.2;
    n.parameters = {
      method: 'POST',
      url: 'https://www.googleapis.com/calendar/v3/calendars/primary/events',
      authentication: 'predefinedCredentialType',
      nodeCredentialType: 'googleCalendarOAuth2Api',
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: "={{ JSON.stringify({ summary: 'Interview: ' + ($('Parse LLM Response').item.json.job_event.job_title || $json.job_id_fuzzy || 'Job') + ($('Parse LLM Response').item.json.job_event.company_name ? ' @ ' + $('Parse LLM Response').item.json.job_event.company_name : ''), description: [($('Parse LLM Response').item.json.job_event.company_name ? '<b>Unternehmen:</b> ' + $('Parse LLM Response').item.json.job_event.company_name : null), ($('Parse LLM Response').item.json.job_event.job_title ? '<b>Position:</b> ' + $('Parse LLM Response').item.json.job_event.job_title : null), ($json.interview_date ? '<b>Datum:</b> ' + String($json.interview_date).substring(0, 10) : null), ($json.stage ? '<b>Phase:</b> ' + $json.stage : null), ($json.priority ? '<b>Prioritaet:</b> ' + $json.priority : null), ($json.job_id_fuzzy ? '<b>ID:</b> ' + $json.job_id_fuzzy : null)].filter(Boolean).join('<br>'), start: { date: String($json.interview_date).substring(0, 10) }, end: { date: String($json.interview_date).substring(0, 10) }, reminders: { useDefault: true } }) }}",
      options: { timeout: 10000 }
    };
    n.credentials = {
      googleCalendarOAuth2Api: {
        id: 'eLQTxfMJ6kryO1Iy',
        name: 'Google Calendar account'
      }
    };
  }

  return n;
});

// Add Telegram node
const telegramNode = {
  id: 'n_telegram_manual',
  name: 'Telegram: Job Alert',
  type: 'n8n-nodes-base.httpRequest',
  typeVersion: 4.2,
  position: [3350, 520],
  parameters: {
    method: 'POST',
    url: '=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage',
    sendBody: true,
    contentType: 'raw',
    rawContentType: 'application/json',
    body: "={{ JSON.stringify({ chat_id: $env.TELEGRAM_CHAT_ID, parse_mode: 'HTML', text: ['\\u{1F514} <b>[JobRadar] ' + ($('Parse LLM Response').item.json.job_event.company_name || 'Unknown') + '</b>', '<b>' + ($('Parse LLM Response').item.json.job_event.job_title || '') + '</b>', '', 'Phase: <code>' + ($json.stage || '') + '</code>  Prioritaet: <b>' + ($json.priority || '') + '</b>', (($('Parse LLM Response').item.json.job_event.salary_min || $('Parse LLM Response').item.json.job_event.salary_max) ? 'Gehalt: ' + [$('Parse LLM Response').item.json.job_event.salary_min, $('Parse LLM Response').item.json.job_event.salary_max].filter(Boolean).join('-') + ' ' + ($('Parse LLM Response').item.json.job_event.salary_currency || '') : null), '', ($json.summary || '')].filter(Boolean).join('\\n') }) }}",
    options: { timeout: 10000 }
  }
};

// Add IF: priority = high node
const ifPriorityNode = {
  id: 'n_if_priority_manual',
  name: 'IF: priority = high',
  type: 'n8n-nodes-base.if',
  typeVersion: 2.2,
  position: [3130, 540],
  parameters: {
    conditions: {
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

clean.nodes.push(ifPriorityNode);
clean.nodes.push(telegramNode);

// Fix connection key renames
if (clean.connections['DeepSeek API']) {
  clean.connections['LLM Call (OpenRouter)'] = clean.connections['DeepSeek API'];
  delete clean.connections['DeepSeek API'];
}
if (clean.connections['Parse DeepSeek Response']) {
  clean.connections['Parse LLM Response'] = clean.connections['Parse DeepSeek Response'];
  delete clean.connections['Parse DeepSeek Response'];
}
// Fix references inside connection values
const connStr = JSON.stringify(clean.connections)
  .replace(/"node":"DeepSeek API"/g, '"node":"LLM Call (OpenRouter)"')
  .replace(/"node":"Parse DeepSeek Response"/g, '"node":"Parse LLM Response"')
  .replace(/"node":"TODO: Google Calendar"/g, '"node":"Google Calendar: Create Event"');
clean.connections = JSON.parse(connStr);

// Add DB: Write All -> IF: priority = high connection (parallel with existing)
if (clean.connections['DB: Write All'] && clean.connections['DB: Write All'].main && clean.connections['DB: Write All'].main[0]) {
  clean.connections['DB: Write All'].main[0].push({
    node: 'IF: priority = high',
    type: 'main',
    index: 0
  });
}

// Add IF: priority = high connections
clean.connections['IF: priority = high'] = {
  main: [
    [{ node: 'Telegram: Job Alert', type: 'main', index: 0 }],
    []
  ]
};

const json = JSON.stringify(clean, null, 2);

// Validate
const remaining = (json.match(/[Ѐ-ӿ]/g) || []).length;
const emptyIds = (json.match(/"id":\s*""/g) || []).length;
console.log('Remaining Cyrillic:', remaining);
console.log('Empty credential IDs:', emptyIds);
console.log('Nodes:', clean.nodes.length);
console.log('Connection keys:', Object.keys(clean.connections).join(', '));

try {
  JSON.parse(json);
  console.log('JSON valid: OK');
} catch (e) {
  console.log('JSON INVALID:', e.message);
  process.exit(1);
}

fs.writeFileSync(dst, json, 'utf8');
console.log('Written:', dst);
