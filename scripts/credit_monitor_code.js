const SCRAPERAPI_KEY = $env.SCRAPERAPI_KEY || '';
const SGAI_KEY = $env.SCRAPEGRAPHAI_KEY || '';
const OR_KEY = $env.OPENROUTER_API_KEY || '';
const THRESHOLD = 20;

async function check(label, fn) {
  try { return { name: label, data: await fn(), ok: true }; }
  catch(e) { return { name: label, ok: false, error: e.message }; }
}

const [scraperResult, sgaiResult, orResult] = await Promise.all([
  check('ScraperAPI', () => helpers.httpRequest({
    method: 'GET',
    url: 'http://api.scraperapi.com/account?api_key=' + SCRAPERAPI_KEY
  })),
  check('SGai', () => helpers.httpRequest({
    method: 'GET',
    url: 'https://api.scrapegraphai.com/v1/credits',
    headers: { 'SGAI-APIKEY': SGAI_KEY }
  })),
  check('OpenRouter', () => helpers.httpRequest({
    method: 'GET',
    url: 'https://openrouter.ai/api/v1/auth/key',
    headers: { 'Authorization': 'Bearer ' + OR_KEY }
  }))
]);

const alerts = [];
const lines = [];

if (!scraperResult.ok) {
  alerts.push('ScraperAPI ERROR: ' + scraperResult.error);
  lines.push('X ScraperAPI: nicht erreichbar');
} else {
  const d = scraperResult.data;
  const remaining = d.requestCount !== undefined ? d.requestCount : (d.credits_remaining || 0);
  const total = d.requestLimit || (remaining + (d.credits_used || 0)) || 1;
  const pct = Math.round(remaining / total * 100);
  lines.push((pct >= THRESHOLD ? 'OK' : 'WARN') + ' ScraperAPI: ' + remaining.toLocaleString() + ' / ' + total.toLocaleString() + ' (' + pct + '%)');
  if (pct < THRESHOLD) alerts.push('WARN ScraperAPI: ' + pct + '% verbleibend');
}

if (!sgaiResult.ok) {
  alerts.push('SGai ERROR: ' + sgaiResult.error);
  lines.push('X SGai: nicht erreichbar');
} else {
  const d = sgaiResult.data;
  const used = d.used || d.credits_used || 0;
  const total = d.limit || d.credits_limit || 500;
  const remaining = total - used;
  const pct = Math.round(remaining / total * 100);
  lines.push((pct >= THRESHOLD ? 'OK' : 'WARN') + ' SGai: ' + remaining + ' / ' + total + ' Credits (' + pct + '%)');
  if (pct < THRESHOLD) alerts.push('WARN SGai: ' + pct + '% verbleibend (' + remaining + ' Credits)');
}

if (!orResult.ok) {
  alerts.push('OpenRouter ERROR: ' + orResult.error);
  lines.push('X OpenRouter: nicht erreichbar');
} else {
  const d = (orResult.data && orResult.data.data) ? orResult.data.data : (orResult.data || {});
  const limit = parseFloat(d.limit) || 25.0;
  const used = parseFloat(d.usage) || 0.0;
  const remaining = parseFloat((limit - used).toFixed(3));
  const pct = Math.round(remaining / limit * 100);
  lines.push((pct >= THRESHOLD ? 'OK' : 'WARN') + ' OpenRouter: $' + remaining + ' / $' + limit + ' (' + pct + '%)');
  if (pct < THRESHOLD) alerts.push('WARN OpenRouter: $' + remaining + ' verbleibend');
}

const hasAlerts = alerts.length > 0;
const now = new Date().toISOString().slice(0,16).replace('T',' ');
const header = hasAlerts ? 'CREDIT ALERT' : 'Credits OK';
const message = header + ' [' + now + ']\n\n' + lines.join('\n') + (hasAlerts ? '\n\n' + alerts.join('\n') : '');

return [{ json: { hasAlerts, message, alerts } }];
