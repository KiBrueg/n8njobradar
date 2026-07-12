// SGai smartscraper — career page batch
// KEY: always use $env.SCRAPEGRAPHAI_KEY — never hardcode
const SGAI_KEY = $env.SCRAPEGRAPHAI_KEY;
const CAREER_PAGES = [
  // --- Germany ---
  { company: 'abiturma',    url: 'https://www.abiturma.de/jobs',                   region: 'Germany' },
  { company: 'Aivitex',     url: 'https://aivitex.com/careers',                    region: 'Germany' },
  { company: 'CANCOM',      url: 'https://www.cancom.com/career/',                 region: 'Germany' },
  { company: 'Fireball Labs',url: 'https://www.fireballlabs.com/jobs',             region: 'Germany' },
  { company: 'Freeletics',  url: 'https://www.freeletics.com/en/jobs/',            region: 'Germany' },
  { company: 'HashiCorp',   url: 'https://www.hashicorp.com/jobs',                region: 'Germany,USA,UK' },
  { company: 'Implisense',  url: 'https://implisense.com/karriere/',               region: 'Germany' },
  { company: 'InfluxData',  url: 'https://www.influxdata.com/careers/',            region: 'Germany,USA,UK' },
  { company: 'Lifen',       url: 'https://www.lifen.health/en/careers',            region: 'Germany,France,UK' },
  { company: 'Link11',      url: 'https://www.link11.com/en/company/careers/',     region: 'Germany' },
  { company: 'vast limits', url: 'https://vastlimits.com/jobs/',                  region: 'Germany' },
  { company: 'Zeit.io',     url: 'https://zeit.io/jobs/',                          region: 'Germany,NL,Spain' },
  { company: 'Zolar',       url: 'https://www.zolar.de/karriere',                 region: 'Germany' },
  // --- Europe ---
  { company: 'Giant Swarm', url: 'https://www.giantswarm.io/careers',             region: 'Europe' },
  { company: 'Checkly',     url: 'https://www.checklyhq.com/jobs/',               region: 'Europe' },
  { company: 'SoftwareMill',url: 'https://softwaremill.com/join-us/',             region: 'Europe' },
  { company: 'Semaphore',   url: 'https://semaphoreci.com/careers',               region: 'Europe' },
  { company: 'Inpsyde',     url: 'https://inpsyde.com/en/jobs/',                  region: 'Europe' },
  { company: 'Quaderno',    url: 'https://quaderno.io/about/',                    region: 'Europe' },
  { company: 'Appinio',     url: 'https://appinio.com/en/careers/',               region: 'Europe' },
  { company: 'Fraudio',     url: 'https://www.fraudio.com/careers/',              region: 'Europe' },
  { company: 'Shareup',     url: 'https://shareup.app/jobs/',                     region: 'Europe' },
  { company: 'journy.io',   url: 'https://www.journy.io/careers',                 region: 'Europe' },
  // --- Initiativbewerbung Targets ---
  { company: 'Datatroniq (GAIA)',         url: 'https://datatroniq.com/de/karriere',               region: 'Germany' },
  { company: 'Antares Capital',           url: 'https://www.antarescapital.com/careers',            region: 'USA,Remote' },
  { company: 'Antares Global',            url: 'https://antaresglobal.com/careers',                 region: 'Global' },
  { company: 'Antares Solutions',         url: 'https://www.antaressolutions.com/careers',          region: 'Global' },
  { company: 'Antares Vision Group',      url: 'https://www.antaresvisionsgroup.com/career',        region: 'Italy,EU' },
  // --- EU AI Startups (funded 2024-2026) ---
  { company: 'Mistral AI',   url: 'https://mistral.ai/careers/',                  region: 'France,EU' },
  { company: 'n8n',          url: 'https://n8n.io/careers/',                      region: 'Germany,Europe' },
  { company: 'Adaptive ML',  url: 'https://www.adaptive-ml.com/jobs',             region: 'France' },
  { company: 'Nscale',       url: 'https://nscale.ai/company/careers/',           region: 'UK,EU' },
  { company: 'Lovable',      url: 'https://lovable.dev/careers/',                 region: 'Sweden,Europe' },
  { company: 'Graphcore',    url: 'https://www.graphcore.ai/careers',             region: 'UK' },
  { company: 'Speechmatics', url: 'https://www.speechmatics.com/company/careers', region: 'UK' },
  { company: 'Together AI',  url: 'https://www.together.ai/careers',              region: 'UK,USA' },
];

const PROMPT = 'Extract all job listings. For each job return a JSON object with: title, location, url (full link to posting), department. Return a JSON array only.';

const results = [];
for (const page of CAREER_PAGES) {
  try {
    const resp = await fetch('https://api.scrapegraphai.com/v1/smartscraper', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'SGAI-APIKEY': SGAI_KEY },
      body: JSON.stringify({ website_url: page.url, user_prompt: PROMPT }),
    });
    const data = await resp.json();
    const jobs = Array.isArray(data.result) ? data.result : [];
    for (const job of jobs) {
      if (!job.title) continue;
      results.push({ json: {
        title:        job.title || '',
        location:     job.location || 'Remote',
        url:          job.url || job.link || page.url,
        department:   job.department || '',
        company:      page.company,
        region:       page.region,
        content:      [job.title, job.department, job.location].join(' '),
        input_source: 'scraped',
        source_url:   page.url,
      }});
    }
  } catch (_) {}
}

return results.length > 0 ? results : [{ json: { _empty: true, company: '', title: '' } }];
