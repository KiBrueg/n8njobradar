# Job Search Prompt — Автоматический поиск

> Промт для ежедневного поиска. Копируй в ChatGPT/Claude или используй как чек-лист.
> Профиль: Python / AI / n8n / Make.com automation freelancer, Gewerbe в Германии (Berlin), remote.

---

## Промт

Du bist mein Job-Search-Assistent. Mein Profil:

**Kirill Brüggemann** — Freelance AI & Automation Engineer (Gewerbe, Berlin)
- Stack: Python, n8n, Make.com, LLM/RAG, Postgres, REST APIs
- Sprachen: Deutsch (C1), Englisch (B2), Russisch (Muttersprache)
- Staatsangehörigkeit: deutsch
- Modell: Remote-Freelancer mit Gewerbeschein — kann an US/EU Firmen auf Rechnung arbeiten (kein Visum nötig)

**Suchbegriffe (kombiniere):**
- `python automation AI engineer remote freelance`
- `n8n Make.com Zapier automation freelance`
- `LLM RAG chatbot developer remote`
- `KI Automatisierung Prozessautomatisierung freelance`
- `AI workflow automation contractor remote`

---

## A. Automatisch gescannt (Flow 7 — 37 Queries, täglich 04:30)

Diese Boards werden automatisch durchsucht — hier nur prüfen wenn Flow 7 ausfällt:

| Board | URL | Typ |
|-------|-----|-----|
| FreelancerMap | freelancermap.de | DE Freelance |
| Malt | malt.de | DE Freelance |
| Freelance.de | freelance.de | DE Freelance |
| GULP | gulp.de | DE Freelance |
| RemoteOK | remoteok.com | Remote |
| WeWorkRemotely | weworkremotely.com | Remote |
| Remotive | remotive.com | Remote |
| Wellfound | wellfound.com | Startups |
| Arc.dev | arc.dev | Remote Dev |
| FlexJobs | flexjobs.com | Remote |
| Jobspresso | jobspresso.co | Remote |
| DynamiteJobs | dynamitejobs.com | Remote |
| NoDesk | nodesk.co | Remote |
| JustRemote | justremote.co | Remote |
| Working Nomads | workingnomads.com | Remote |
| Authentic Jobs | authenticjobs.com | Remote |
| JobRack | jobrack.eu | EU Remote |
| web3.career | web3.career | Web3 |
| Jobgether | jobgether.com | EU Remote |
| BuiltIn | builtin.com | Tech |
| Toptal | toptal.com | US Contractor |
| Turing | turing.com | US Contractor |
| Gun.io | gun.io | US Contractor |
| Contra | contra.com | Freelance |
| Lemon.io | lemon.io | US Contractor |
| Feedcoyote | feedcoyote.com | Freelance |
| Himalayas | himalayas.app | Remote |
| JobBoardSearch | jobboardsearch.com | Remote |
| Virtual Vocations | virtualvocations.com | Remote |
| Hokify | hokify.de | DE |
| StudySmarter | talents.studysmarter.de | DE |
| Remote3 | remote3.co | Web3 |
| Jobs im Südwesten | jobs-im-suedwesten.de | DE Regional |
| Hubstaff Talent | talent.hubstaff.com | Freelance |
| Crossover | crossover.com | Remote Contractor |
| Remote.co | remote.co | Remote |
| Remote Woman | remotewomen.com | Remote (placeholder) |

---

## B. Nicht automatisch parsbar — manuell prüfen (2–3x/Woche)

Diese Boards blockieren Scraping oder erfordern Login. Hier manuell suchen:

### Tier 1 — Höchste Priorität (täglich)

| Board | URL | Warum manuell |
|-------|-----|---------------|
| **LinkedIn** | linkedin.com/jobs | Login-Wall, Anti-Scraping. Filter: "Remote" + "AI automation" + "Python". Auch Recruiter-Posts checken |
| **Upwork** | upwork.com | Bidding-Plattform, Login nötig. Suche: "n8n automation", "AI workflow", "Python automation". Proposals senden |
| **Indeed** | de.indeed.com | Anti-Scraping. Suche: "AI Automatisierung remote", "Python Freelance" |

### Tier 2 — Hohe Priorität (3x/Woche)

| Board | URL | Warum manuell |
|-------|-----|---------------|
| **Xing** | xing.com/jobs | Login-Wall. Deutsch-sprachige Projekte, "Automatisierung", "KI Engineer" |
| **StepStone** | stepstone.de | Anti-Bot. Suche: "AI Automation Engineer remote" |
| **Glassdoor** | glassdoor.de | Login-Wall. Auch für Gehaltsrecherche + Company Reviews |
| **Fiverr** | fiverr.com | Marketplace-Modell. Eigene Gigs erstellen: "n8n automation", "AI chatbot", "workflow automation" |
| **Freelancer.com** | freelancer.com | Bidding. Suche: "python automation", "n8n", "AI bot" |
| **PeoplePerHour** | peopleperhour.com | UK-lastig, Login nötig. "Python automation", "AI workflow" |
| **ZipRecruiter** | ziprecruiter.com | US-focused, Anti-Bot. "AI automation engineer remote" |
| **Guru** | guru.com | Freelance marketplace, Login nötig |
| **PowerToFly** | powertofly.com | Diversity + remote, Login nötig |

### Tier 3 — Wöchentlich

| Board | URL | Warum manuell |
|-------|-----|---------------|
| **Hacker News** | news.ycombinator.com (Who is Hiring) | Monatlicher Thread (1. des Monats). Suche: "remote", "automation", "AI" |
| **Reddit** | r/forhire, r/remotejs, r/freelance | Posts durchscrollen, auf "[Hiring]" filtern |
| **Dribbble** | dribbble.com/jobs | Eher Design, aber auch "Automation Developer" |
| **GitHub Jobs** | github.com/trending → README job boards | Community-Listen, awesome-remote-job |
| **Wolt/Delivery Hero/N26 Careers** | Direkt auf Karriereseiten | Berliner Tech-Firmen, oft unlisted remote roles |
| **YC Work at a Startup** | workatastartup.com | YC-Portfolio, Login nötig. "AI", "Automation" |
| **AngelList Talent** | angel.co/talent | Startup-Jobs, Equity+Cash Modelle |

### Tier 4 — Nischen (monatlich checken)

| Board | URL | Nische |
|-------|-----|--------|
| **Braintrust** | usebraintrust.com | Web3/DAO Freelance, Token-basiert |
| **Pangian** | pangian.com | Remote-only Community |
| ~~Hubstaff Talent~~ | ~~talent.hubstaff.com~~ | → автоскан Flow 7 |
| **Outsourcely** | outsourcely.com | Startup remote jobs |
| **Codementor** | codementor.io | Mentoring + Freelance dev |
| **DataJobs.com** | datajobs.com | Data/ML spezifisch |
| **AI-Jobs.net** | ai-jobs.net | Pure AI job board |
| **MLconf Jobs** | jobs.mlconf.com | ML/AI Konferenzen-Board |

---

## C. Suchstrategie-Tipps

1. **LinkedIn:** Alerts einrichten für "AI automation engineer remote" + "n8n freelance" — Push-Benachrichtigungen
2. **Upwork:** Profil optimieren mit "n8n certified", Spezialisierung auf AI Workflow Automation
3. **Toptal/Turing/Lemon.io:** Einmal bewerben → Pipeline. Screening bestehen = dauerhafter Zugang
4. **Direktansprache:** Berliner Startups direkt via LinkedIn/Email kontaktieren (N26, Delivery Hero, Gorillas alumni, Trade Republic)
5. **Gewerbe-Vorteil betonen:** "Available as contractor, invoice-based, no visa sponsorship needed" — senkt die Hiring-Hürde für US/UK Firmen
6. **GitHub Profil:** Pinned repos mit n8n/automation Projekten → Recruiter sehen es bei Google-Suche
