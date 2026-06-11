# Stage 1 Test Results

> Date: 2026-06-08  
> Prompt version: prompt-system.txt (initial)  
> Method: Manual application of prompt rules to each test case  
> Legend: ✅ correct · ⚠️ partial / ambiguous · ❌ wrong / missing

---

## Case 01 — Newsletter (StepStone digest)

**Expected:** `is_job_related: false`, `category: newsletter`, `action: ignore`

**Result:** ✅ All correct.  
The sender domain `newsletter@stepstone.de` + mass content + unsubscribe link = clear newsletter signal. Prompt rule fires correctly.

**Issues:** None.

---

## Case 02 — Mass HR Invite (Acme Solutions)

**Expected:** `is_job_related: true`, `category: hr_invite`, `priority_level: 2`, `stage: discovered`

**Result:** ⚠️ Mostly correct, one ambiguity.

- `is_job_related`, `category`, `salary`, `work_mode` → ✅
- `priority_level: 2` → ⚠️ **RISK**: The email says "I came across your profile" — this sounds personal but is a classic mass template. The prompt's rule for priority_level 1 says "personally addresses candidate by name, references their profile." This email does NOT use the candidate's name and doesn't reference specific profile details → should be 2. But a weak model might give it 1.
- `stage: discovered` → ✅ correct (no confirmed interest from candidate yet, just an inbound invite)
- `company_id: "acme-solutions-gmbh"` → ⚠️ **RISK**: Model might produce `"acme-solutions"` (dropping GmbH) or `"acme-solutions-ag"`. Slug rule needs to be more explicit about when to keep/drop legal suffixes.

**Issues found:**
- **BUG-01:** Priority ambiguity — "I came across your profile" language can fool the model into priority 1. Need explicit rule: "generic phrases like 'I came across your profile' without candidate's NAME = priority 2."
- **BUG-02:** company_id slugging for legal suffixes (GmbH, AG, SE, Ltd, Inc) — needs a normalization rule.

---

## Case 03 — Personal Interview Invite (N26, Kirill)

**Expected:** `priority_level: 1`, `interview_date: 2026-06-16T14:00:00Z`, `call_platform: google_meet`, `response_deadline: 2026-06-10`

**Result:** ⚠️ Mostly correct, date timezone issue.

- `is_job_related`, `category: interview_invite`, `stage: interview`, `priority: high` → ✅
- `employer_id: anna.mueller@n26.com` → ✅
- `salary: 85000–105000 EUR/year` → ✅
- `call_platform: google_meet` → ✅ ("I'll send the meeting link separately" is ambiguous, but "via Google Meet" is explicit)
- `interview_date` → ⚠️ **RISK**: "3:00 PM CET" = UTC+2 in June → 13:00 UTC. Prompt says "time without timezone → assume UTC." But CET is explicitly stated. Model must convert CET→UTC, not just strip timezone. Expected: `2026-06-16T13:00:00Z`, not `2026-06-16T15:00:00Z` (wrong) or `2026-06-16T14:00:00Z` (wrong, that's CEST confusion).
- `response_deadline: 2026-06-10` → ✅

**Issues found:**
- **BUG-03:** Timezone conversion — the prompt says "if no timezone → assume UTC" but doesn't tell the model HOW to convert named timezones (CET=UTC+1, CEST=UTC+2). Model may store wrong UTC time or skip conversion entirely.

---

## Case 04 — Job Offer (Fintech Ventures)

**Expected:** `stage: offer`, `salary: 92000/92000`, `response_deadline: 2026-06-20`

**Result:** ✅ All correct.

- Single salary value → both min and max set to 92000 → ✅ (explicit rule in prompt)
- `response_deadline: "June 20, 2026"` → `2026-06-20` → ✅
- `call_platform: null` → ✅ (no call mentioned)
- `has_had_call: false` → ⚠️ **RISK**: The email says "we look forward to welcoming you" after an offer — implies there was a prior interview process. BUT the text doesn't explicitly mention a past call. Prompt rule: "true ONLY if text EXPLICITLY mentions a past call." So `false` is correct here — but a model might infer `true` from context.

**Issues found:**
- **BUG-04:** `has_had_call` over-inference — model might set `true` based on implicit context (offer = obviously had interview). Rule needs stronger emphasis: "Only from explicit text mention."

---

## Case 05 — Rejection (CloudBase AG)

**Expected:** `stage: rejected`, `has_had_call: true`

**Result:** ✅ Correct.

- "thank you for taking the time to **interview** with us" → `has_had_call: true` → ✅ (explicit mention)
- `stage: rejected` → ✅
- `priority_level: 1` → ⚠️ **RISK**: After rejection, priority arguably drops to low/irrelevant. But the prompt has no rule for downgrading priority on rejection. Should rejections auto-downgrade to `priority_level: 3`? Design question, not a prompt bug per se.

**Issues found:**
- **DESIGN-01:** Should `priority_level` be downgraded to 3 on rejection? Currently prompt has no such rule → priority stays at whatever was set before. Discuss.

---

## Case 06 — Test Task (DataFlow GmbH, SRE)

**Expected:** `stage: test_task`, `response_deadline: 2026-06-14`, `has_had_call: true`, `tech_stack: [Python, Prometheus, Grafana, Docker]`

**Result:** ⚠️ Mostly correct, deadline edge case.

- `stage: test_task`, `category: test_task` → ✅
- `has_had_call: true` ("Great speaking with you yesterday") → ✅
- `tech_stack: [Prometheus, Grafana, Docker]` → ⚠️ **RISK**: Python is mentioned implicitly ("Python & DevOps Bootcamp" in task description — actually NOT in this email). Docker Compose is in the task, Docker should be extracted. But **Compose** is an add-on, not a separate technology. Model might over-extract ("Docker Compose" as one item, or extract "GitHub" as tech_stack which is wrong).
- `response_deadline: 2026-06-14` → ✅ ("submit by June 14, 2026")
- `job_title: "Site Reliability Engineer"` → ✅

**Issues found:**
- **BUG-05:** `tech_stack` over-extraction — "GitHub" as a submission platform might be extracted as a tech. Need rule: "Do not include version control platforms (GitHub, GitLab, Bitbucket) as tech_stack unless the role explicitly requires Git expertise."

---

## Case 07 — Noisy Course Ad

**Expected:** `is_job_related: false`, `action: ignore`

**Result:** ⚠️ RISKY case.

- The email contains keywords: "tech vacancies", "jobs", "Python", "DevOps", "Kubernetes", "Google", "Amazon"
- **HIGH RISK**: A weak/confused model might set `is_job_related: true` and `category: job_posting` because of the heavy job-related vocabulary.
- The key signals for `false`: sender is a promotional domain, no direct job offer to the candidate, contains "enroll now", "discount", "unsubscribe", "bootcamp".

**Issues found:**
- **BUG-06:** `is_job_related` false-positive on course ads. The prompt's rule says "marketing newsletter with no specific job offer for the user" → ignore. But the rule for `is_job_related: true` says "any text describing a specific job" — and the ad does list job titles (Backend Developer, DevOps Engineer...). Need to add explicit anti-pattern: "Job listings that belong to a third-party site (job board) being pitched as a product/course are NOT direct job offers to the candidate → is_job_related: false."

---

## Case 08 — No-Salary Job Posting (Zalando Staff Engineer)

**Expected:** `salary_*: all null`, `source_url` extracted, `seniority: staff`

**Result:** ✅ All correct.

- "We do not publish salary information" → explicit statement → all salary fields null → ✅
- `seniority: staff` → ✅ (title contains "Staff Engineer")
- `source_url: "https://jobs.zalando.com/..."` → ✅ (from raw_meta.url)
- `work_mode: hybrid` → ✅ ("Hybrid" explicit)

**Issues:** None for this case.

---

## Case 09 — Ambiguous Relative Date ("this Friday")

**Expected:** `interview_date: 2026-06-12T11:00:00Z` (email sent 2026-06-08 = Monday, "this Friday" = June 12)

**Result:** ❌ HIGH RISK.

The prompt says: "Year not stated → assume 2026. Time without timezone → assume UTC." But it does NOT tell the model HOW to resolve relative dates like "this Friday", "next Monday", "in two weeks."

A model must:
1. Know the email_date (2026-06-08, Monday)
2. Calculate "this Friday" = 2026-06-12
3. "11am" with no timezone → assume UTC → 2026-06-12T11:00:00Z

**Problems:**
- The model receives `date: "2026-06-08T13:00:00Z"` in the input — it CAN use this as anchor.
- But the prompt has no explicit rule for relative date resolution.
- Models often hallucinate specific dates from relative terms or return null.

**Issues found:**
- **BUG-07 (CRITICAL):** No rule for resolving relative date expressions ("this Friday", "next Tuesday", "tomorrow", "in two weeks", "end of the week"). Model has the `date` field in input to use as anchor but the prompt never instructs it to do this calculation. High probability of either null or hallucinated date.

---

## Case 10 — Follow-up (Scale AI)

**Expected:** `category: follow_up`, `has_had_call: true`, `response_deadline: 2026-06-12`

**Result:** ⚠️ Mostly correct, deadline ambiguity.

- `has_had_call: true` ("your interview last Thursday") → ✅ explicit mention
- `category: follow_up` → ✅
- `stage: interview` → ✅ (still in interview stage, decision pending)
- `response_deadline` → ⚠️ "by end of this week (Friday, June 12)" → model must parse "(Friday, June 12)" from parenthetical and resolve to `2026-06-12`. The explicit "June 12" is there, so this should work — but the phrasing "end of this week" is the primary statement, the date is a clarification. Model might set deadline to null if it doesn't parse the parenthetical.

**Issues found:**
- **BUG-08:** Deadline extraction from parenthetical clarifications — "by end of this week (Friday, June 12)" — the model should prefer the explicit date in parentheses. Needs a rule: "If a relative time expression is followed by an explicit date clarification in parentheses, use the explicit date."

---

## Summary of Issues Found

| ID | Severity | Description |
|----|----------|-------------|
| BUG-01 | HIGH | Priority ambiguity: "I came across your profile" without candidate name → should be 2, not 1 |
| BUG-02 | MEDIUM | company_id slugging: inconsistent handling of GmbH/AG/SE/Ltd/Inc legal suffixes |
| BUG-03 | HIGH | Timezone conversion: named TZ (CET/CEST/EST) not converted to UTC correctly |
| BUG-04 | MEDIUM | has_had_call over-inference from implicit context (offer implies prior interview) |
| BUG-05 | LOW | tech_stack over-extraction: GitHub/GitLab as submission platforms included as tech |
| BUG-06 | HIGH | is_job_related false-positive: course/bootcamp ads with job keywords → wrongly flagged as true |
| BUG-07 | CRITICAL | Relative date resolution: "this Friday", "next Tuesday", etc. — no anchor rule in prompt |
| BUG-08 | MEDIUM | Deadline from parenthetical: "by end of week (June 12)" — explicit date in parens may be missed |
| DESIGN-01 | LOW | priority_level on rejection: should it auto-downgrade to 3? (design decision, not a bug) |

---

## Fixes Required in prompt-system.txt

1. **BUG-07 (CRITICAL):** Add relative date resolution rule using `date` field as anchor.
2. **BUG-03 (HIGH):** Add named timezone → UTC conversion table (CET, CEST, EST, MSK, etc.).
3. **BUG-01 (HIGH):** Sharpen priority_level 1 rule — require candidate's NAME in the email.
4. **BUG-06 (HIGH):** Add explicit rule for course/bootcamp ads even when job keywords are dense.
5. **BUG-02 (MEDIUM):** Add company_id slug rule for legal suffixes.
6. **BUG-04 (MEDIUM):** Add "explicit text only" emphasis to has_had_call.
7. **BUG-08 (MEDIUM):** Add parenthetical date clarification rule.
8. **BUG-05 (LOW):** Add negative example for tech_stack (exclude submission platforms).
