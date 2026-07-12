# Job Search Prompt — Автоматический поиск

> Промт для ежедневного поиска. Копируй в ChatGPT/Claude или используй как чек-лист.
> Профиль: Python / AI / n8n / Make.com automation freelancer, Gewerbe в Германии (Berlin), remote.

---

## Промт

Du bist mein Job-Search-Assistent. Mein Profil:

**Kirill Brüggemann** — Freelance AI & Automation Engineer (Gewerbe, Berlin)
- Stack: Python, n8n, Make.com, LLM/RAG, Postgres, REST APIs, Docker, pgvector
- Projekte: JobRadar (Multi-Source AI Pipeline, 39-Feld JSON, PostgreSQL), Crypto Intel Agent (Investment-Signal-Pipeline, Multi-Agenten-Architektur, CoinGecko/DexScreener/Binance), Telegram-Bots (async Python, FastAPI)
- Sprachen: Deutsch (C1), Englisch (B2), Russisch (Muttersprache)
- Staatsangehörigkeit: deutsch — kein Visum nötig, kann an EU/US-Firmen auf Rechnung arbeiten
- Arbeitsform: Nur Remote. Kein Hybrid, kein Büro, kein Umzug.
- GitHub: github.com/KiBrueg

**Ich suche (alle Typen gleichzeitig):**
- **Vollzeit (Angestellt)** — AI/Automation/Python Engineer, 55–95k EUR/Jahr, Remote
- **Teilzeit / Werkstudent** — 20–30h/Woche, remote, AI/n8n/Python
- **Praktikum** — remote, bezahlt, min. 3 Monate, AI/Automation/Python
- **Freelance / Projektauftrag** — Einzel-Tasks oder laufende Projekte, n8n, Python, LLM, API-Integration

**Suchbegriffe (kombiniere):**
- `n8n automation engineer remote`
- `python AI automation engineer remote`
- `LLM RAG chatbot developer remote`
- `KI Automatisierung Prozessautomatisierung remote`
- `AI workflow automation freelance`
- `make.com integromat automation`
- `API integration python freelance`
- `AI agent developer remote`

---

## Wichtige Hinweise für maximale Trefferquote

- **n8n explizit im Stack** = sofort Top-Priorität (sehr seltener Skill in Stellenanzeigen)
- **Mittelstand + KI** = guter Fit (ich spreche Deutsch, erkläre Technik verständlich)
- **Kein SAP/Enterprise ohne Erfahrung** — nicht vorschlagen
- **Kein Frontend-only** — Backend, Pipelines, Automatisierung ist mein Kern
- **Remote ist Pflicht** — kein Hybrid, kein Büro, kein Umzug
- **Gehalt unter 45k** = nicht ideal, aber kein Ausschlusskriterium — Stelle finden ist wichtiger als auf Gehalt zu bestehen. Trotzdem erwähnen.
- **SAP:** Normalerweise kein produktiver Einsatz — ABER: wenn die Stelle 100% Remote ist und explizit Einsteiger/Quereinsteiger akzeptiert, vorschlagen. Ich habe 2 SAP-Demo-Projekte als Nachweis.
- **Freelance-Aufträge:** Machbarkeit bewerten — nicht ob ich den Stack persönlich beherrsche, sondern ob er mit KI-Unterstützung (Claude) lieferbar ist. Java, .NET, PHP, JS-Frameworks usw. sind alle machbar wenn das Endergebnis ein fertiges Produkt ist. Ausschlusskriterium nur wenn echtes On-Site-Debugging oder Enterprise-Zugang ohne Testumgebung nötig ist.
- **Bewerbung läuft bereits bei:** StackFuel, COREEN, RoX, BIT Capital, Team Passerelle — diese nicht nochmal vorschlagen

---

## A. Flow 7 — SerpAPI (51 Queries, täglich 04:30)

Automatische Google-SERP-Suche mit `site:` Operator. Ergebnisse → LLM → Postgres → Notion.

### DE Freelance Plattformen
| Label | Site | Query-Fokus |
|-------|------|-------------|
| fm-python-n8n | freelancermap.de | python n8n automation freelance remote |
| fm-ki-llm | freelancermap.de | KI LLM Automatisierung freelance remote |
| fm-make | freelancermap.de | Make.com Zapier Automatisierung freelance |
| fm-chatbot | freelancermap.de | chatbot KI Assistent freelance remote |
| malt-python | malt.de | python automation freelance remote |
| malt-n8n | malt.de | n8n automatisierung freelance |
| fd-python | freelance.de | python automation remote freelance |
| gulp-python | gulp.de | python automation remote |

### DE / EU Job Boards
| Label | Site | Query-Fokus |
|-------|------|-------------|
| jisw-ai | jobs-im-suedwesten.de | AI automation engineer remote |
| studysmart-ai | talents.studysmarter.de | AI engineer remote vollzeit teilzeit |
| hokify-ai | hokify.de | AI automation engineer remote |
| remote3-web3 | remote3.co | AI engineer automation remote web3 |

### EU Remote Boards
| Label | Site | Query-Fokus |
|-------|------|-------------|
| remoteok-ai | remoteok.com | python automation AI engineer remote europe |
| wwr-ai | weworkremotely.com | python automation AI engineer |
| remotive-ai | remotive.com | python automation AI remote europe |
| wellfound-ai | wellfound.com | AI automation engineer remote europe |
| arcdev-ai | arc.dev | python automation AI remote |
| flexjobs-ai | flexjobs.com | python automation AI remote europe |
| jobspresso-ai | jobspresso.co | python automation AI remote |
| dynamite-ai | dynamitejobs.com | python automation AI remote |
| nodesk-ai | nodesk.co | python automation AI remote |
| justremote-ai | justremote.co | python automation AI engineer |
| worknomads-ai | workingnomads.com | python automation AI remote |
| authentic-ai | authenticjobs.com | python automation developer remote |
| jobrack-ai | jobrack.eu | python automation AI developer remote |
| web3career-ai | web3.career | python automation AI remote |
| jobgether-ai | jobgether.com | python automation AI remote europe |
| builtin-ai | builtin.com | python automation AI remote |
| himalayas-ai | himalayas.app | python automation AI remote europe |
| jobboardsearch-ai | jobboardsearch.com | python automation AI remote |
| virtualvoc-ai | virtualvocations.com | python automation AI remote |
| hubstaff-ai | talent.hubstaff.com | python automation AI remote |
| crossover-ai | crossover.com | python automation AI remote |
| remoteco-ai | remote.co | python automation AI remote |
| pangian-ai | pangian.com | python automation AI remote *(добавлен 10.07)* |

### US Contractor (Gewerbe-Rechnung, kein Visum)
| Label | Site | Query-Fokus |
|-------|------|-------------|
| toptal-ai | toptal.com | python automation AI freelance |
| turing-ai | turing.com | python automation AI remote |
| gunio-ai | gun.io | python automation freelance |
| contra-ai | contra.com | python automation AI freelance |
| lemon-ai | lemon.io | python automation AI developer |
| feedcoyote-ai | feedcoyote.com | python automation AI freelance |
| upwork-ai | upwork.com | n8n python AI automation freelance *(добавлен 10.07)* |
| junico-ai | junico.de | python n8n automation freelance *(профиль: kirill-9, добавлен 12.07)* |

### Aggregatoren + Dev Boards
| Label | Site | Query-Fokus |
|-------|------|-------------|
| ratrace-ai | ratracerebellion.com | python automation AI remote |
| so-ai | stackoverflow.com/jobs | python automation AI remote |
| careerjet-ai | careerjet.com | python automation AI remote freelance |
| jooble-ai | jooble.org | python automation AI remote |
| remoterocketship-ai | remoterocketship.com | python automation AI engineer remote |
| simplyhired-ai | simplyhired.com | python automation AI remote |
| outsourcey-ai | outsourcey.com | python automation AI remote *(neu 12.07)* |
| skipthedrive-ai | skipthedrive.com | python automation AI remote engineer *(neu 12.07)* |

---

## B. Flow 2 — Web Scraper (Crawl4AI + Jina, täglich 04:00)

Direktes Scrapen von Listing-Seiten. Cloudflare-blockierte Sites → Jina AI.

| Label | Site | Scraper | URL-Pfad |
|-------|------|---------|----------|
| berlinstartupjobs-engineering | berlinstartupjobs.com | crawl4ai | /engineering/ |
| remotely-ai-automation | remotely.de | crawl4ai | /jobs/ai-automation |
| devjobs-automation | devjobs.de | jina | ?q=automation+engineer+remote |
| wwr-automation | weworkremotely.com | crawl4ai | /search?term=automation+engineer |
| xing-automation | xing.com/jobs | jina | ?keywords=automation+engineer+n8n+KI |
| stepstone-python | stepstone.de | jina | /jobs/python?homeOffice=2 |
| stepstone-automation | stepstone.de | jina | /jobs/automatisierung?homeOffice=2 |
| stepstone-ki | stepstone.de | jina | /jobs/ki-entwickler?homeOffice=2 |
| stepstone-praktikum-python | stepstone.de | jina | /jobs/praktikum-python?homeOffice=2 |
| stepstone-werkstudent | stepstone.de | jina | /jobs/werkstudent-python?homeOffice=2 |
| indeed-python | de.indeed.com | jina | ?q=python+automatisierung&l=remote |
| indeed-n8n-ki | de.indeed.com | jina | ?q=n8n+ki+automatisierung |
| indeed-praktikum | de.indeed.com | jina | ?q=python+KI+praktikum&jt=internship |
| monster-python | monster.de | jina | ?q=python-automatisierung&where=remote |
| jobboerse-python | arbeitsagentur.de | crawl4ai | was=Python+Automatisierung |
| jobboerse-ki | arbeitsagentur.de | crawl4ai | was=KI+Entwickler |
| jobboerse-praktikum | arbeitsagentur.de | crawl4ai | angebotsart=34 (Praktikum) |
| heise-python | jobs.heise.de | crawl4ai | ?q=python+automation&remote=true |

---

## C. Flow 2b — Career Pages Direct (SGai Smartscraper, täglich 06:00)

Direktes Scrapen von Karriere-Seiten der Zielfirmen. Ergebnisse → LLM → Postgres → Notion.

### DE Companies (Greenhouse/Ashby API)
| Node | Company | API |
|------|---------|-----|
| GH: Celonis | Celonis | greenhouse |
| GH: HelloFresh | HelloFresh | greenhouse |
| GH: N26 | N26 | greenhouse |
| GH: GetYourGuide | GetYourGuide | greenhouse |
| GH: SumUp | SumUp | greenhouse |
| GH: Contentful | Contentful | greenhouse |
| Ashby: Aleph Alpha | Aleph Alpha | ashby |

### SGai Career Pages Batch (31 URLs)

| Company | Region | URL |
|---------|--------|-----|
| abiturma | Germany | abiturma.de/jobs |
| Aivitex | Germany | aivitex.com/careers |
| CANCOM | Germany | cancom.com/career |
| Fireball Labs | Germany | fireballlabs.com/jobs |
| Freeletics | Germany | freeletics.com/en/jobs |
| HashiCorp | DE+US+UK | hashicorp.com/jobs |
| Implisense | Germany | implisense.com/karriere |
| InfluxData | DE+US+UK | influxdata.com/careers |
| Lifen | DE+FR+UK | lifen.health/en/careers |
| Link11 | Germany | link11.com/careers |
| vast limits | Germany | vastlimits.com/jobs |
| Zeit.io | DE+NL+ES | zeit.io/jobs |
| Zolar | Germany | zolar.de/karriere |
| Giant Swarm | Europe | giantswarm.io/careers |
| Checkly | Europe | checklyhq.com/jobs |
| SoftwareMill | Europe | softwaremill.com/join-us |
| Semaphore | Europe | semaphoreci.com/careers |
| Inpsyde | Europe | inpsyde.com/en/jobs |
| Quaderno | Europe | quaderno.io/about |
| Appinio | Europe | appinio.com/en/careers |
| Fraudio | Europe | fraudio.com/careers |
| Shareup | Europe | shareup.app/jobs |
| journy.io | Europe | journy.io/careers |
| **Mistral AI** | France,EU | mistral.ai/careers *(neu 12.07)* |
| **n8n** | Germany,EU | n8n.io/careers *(neu 12.07)* |
| **Adaptive ML** | France | adaptive-ml.com/jobs *(neu 12.07)* |
| **Nscale** | UK,EU | nscale.ai/company/careers *(neu 12.07)* |
| **Lovable** | Sweden,EU | lovable.dev/careers *(neu 12.07)* |
| **Graphcore** | UK | graphcore.ai/careers *(neu 12.07)* |
| **Speechmatics** | UK | speechmatics.com/company/careers *(neu 12.07)* |
| **Together AI** | UK,USA | together.ai/careers *(neu 12.07)* |

> Nicht aufgenommen: Peltarion (→ Palantir), Sketchfab (→ Epic), Hazy (→ SAS), Synthace/LabGenius (Biotech), VoxelVision/Lumiere AI/Synthara (unklar).

---

## D. Gmail + IMAP (Flow 1 + Flow 3, kontinuierlich)

- **Gmail** (brueggemannkirill@gmail.com) — Job-Benachrichtigungen, HR-Nachrichten, Recruiter-Mails
- **mail.de** (ogi-ogi@mail.de) — IMAP, deutsche Job-Plattform-Notifications

---

## E. Manuell prüfen (2–3x/Woche)

### Tier 1 — täglich

| Board | URL | Aktion |
|-------|-----|--------|
| **LinkedIn** | linkedin.com/jobs | Filter: Remote + AI automation + Python. Auch Recruiter-Posts |
| **Upwork** | upwork.com | Proposals: "n8n automation", "AI workflow", "Python automation" |
| **Hired** | hired.com | Profil pflegen — Unternehmen schreiben direkt |
| **Indeed** | de.indeed.com | Anti-Scraping. Suche manuell |

### Tier 2 — 3x/Woche

| Board | URL | Aktion |
|-------|-----|--------|
| **Xing** | xing.com/jobs | DE-Projekte: "Automatisierung", "KI Engineer" |
| **StepStone** | stepstone.de | Anti-Bot. Manuelle Suche |
| **Glassdoor** | glassdoor.de | Login-Wall + Gehaltsrecherche |
| **Fiverr** | fiverr.com | Eigene Gigs: "n8n automation", "AI chatbot" |
| **Freelancer.com** | freelancer.com | Bidding: "python automation", "n8n" |
| **PeoplePerHour** | peopleperhour.com | "Python automation", "AI workflow" |
| **ZipRecruiter** | ziprecruiter.com | US-focused. "AI automation engineer remote" |
| **Guru** | guru.com | Freelance marketplace |

---

## Output-Format (wie du mir Ergebnisse meldest)

### 🏆 TOP 10 nach Matching (gemischt — Jobs + Freelance)

```
#N [Typ: Job / Freelance / Praktikum / Teilzeit] Matching: X/10
Firma: ...
Rolle: ...
Stack-Match: [was passt]
Lücken: [was fehlt]
Gehalt/Rate: ...
Link: ...
```

---

### 💼 TOP 5 Jobs (Angestellt / Teilzeit / Praktikum)

| # | Firma | Rolle | Typ | Gehalt | Matching | Machbarkeit | Link |
|---|-------|-------|-----|--------|----------|-------------|------|

**Machbarkeit:** Kann ich sofort anfangen? (Ja / Teilweise / Nein + Begründung)

---

### 🔧 TOP 5 Freelance-Aufträge

| # | Auftraggeber | Aufgabe | Budget/Rate | Matching | Machbarkeit | Link |
|---|--------------|---------|-------------|----------|-------------|------|

**Machbarkeit:** Zeitaufwand + ob Stack vollständig bekannt.

---

### ❌ Ausschlussliste
- Bereits beworben: StackFuel, COREEN, RoX, BIT Capital, Team Passerelle, teclift, API-Systemintegration (Rashin Roshan)
- Abgelehnt: uNaice, Kevin Meyer Consulting, GameDuell
- Kein SAP, kein Frontend-only, kein Hybrid/Büro/Umzug, kein Java/.NET/PHP

---

*Letzte Aktualisierung: 2026-07-12 | Flow 7: 51 Queries (Search Queries fixed) | Flow 2: 18 Scrape-Targets | Flow 2b: 31 Career Pages (7 API + 31 SGai) | Flow 9: Praktikum Outreach (auto, personalisiert)*
