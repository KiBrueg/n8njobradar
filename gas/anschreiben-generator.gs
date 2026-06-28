// ============================================================
// JobRadar — Anschreiben Generator
// Добавить в тот же GAS-проект что и sheets-writer.gs
//
// Script Properties (Project Settings → Script properties):
//   OPENROUTER_KEY     — твой OpenRouter API ключ
//   LETTERS_FOLDER_ID  — ID папки Google Drive для писем
//
// Как получить LETTERS_FOLDER_ID:
//   1. Создать папку в Google Drive: "JobRadar / Anschreiben"
//   2. Открыть папку → URL: drive.google.com/drive/folders/<ID>
//   3. <ID> — это и есть LETTERS_FOLDER_ID
// ============================================================

/**
 * Генерирует мотивационное письмо через OpenRouter,
 * сохраняет как Google Doc в Drive, возвращает URL.
 *
 * @param {Object} job { company, job_title, location, employer_name, summary }
 * @returns {string|null} URL Google Doc или null при ошибке
 */
function generateAnschreiben(job) {
  const props        = PropertiesService.getScriptProperties();
  const apiKey       = props.getProperty('OPENROUTER_KEY');
  const folderId     = props.getProperty('LETTERS_FOLDER_ID');

  if (!apiKey || !folderId) {
    Logger.log('Missing Script Properties: OPENROUTER_KEY or LETTERS_FOLDER_ID');
    return null;
  }

  // ── 1. Build prompt ─────────────────────────────────────────
  const prompt = buildPrompt(job);

  // ── 2. Call OpenRouter (Qwen3) ───────────────────────────────
  let letterText;
  try {
    const response = UrlFetchApp.fetch(
      'https://openrouter.ai/api/v1/chat/completions',
      {
        method:             'POST',
        muteHttpExceptions: true,
        headers: {
          'Authorization': 'Bearer ' + apiKey,
          'Content-Type':  'application/json',
          'HTTP-Referer':  'https://jobradar.app',
          'X-Title':       'JobRadar Anschreiben'
        },
        payload: JSON.stringify({
          model:      'qwen/qwen3-30b-a3b-instruct-2507',
          max_tokens: 1500,
          messages:   [{ role: 'user', content: prompt }]
        })
      }
    );

    if (response.getResponseCode() !== 200) {
      Logger.log('OpenRouter error: ' + response.getContentText());
      return null;
    }

    let raw = JSON.parse(response.getContentText()).choices[0].message.content || '';

    // Strip Qwen3 <think>...</think> blocks
    raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();

    // Strip markdown fences if any
    raw = raw.replace(/^```[a-z]*\n?/i, '').replace(/\n?```$/i, '').trim();

    letterText = raw;

  } catch (err) {
    Logger.log('generateAnschreiben error: ' + err.message);
    return null;
  }

  // ── 3. Create Google Doc ─────────────────────────────────────
  try {
    const today   = Utilities.formatDate(new Date(), 'Europe/Berlin', 'yyyy-MM-dd');
    const docName = 'Anschreiben — ' + (job.company || 'Unbekannt')
                  + ' — ' + (job.job_title || 'Stelle')
                  + ' — ' + today;

    // Create doc (appears in Drive root first)
    const doc  = DocumentApp.create(docName);
    const body = doc.getBody();

    // Write content — paragraphs split on \n\n
    body.clear();
    const paragraphs = letterText.split(/\n\n+/);
    paragraphs.forEach(function(para, i) {
      if (i === 0) {
        body.editAsText().setText(para.trim());
      } else {
        body.appendParagraph(para.trim());
      }
    });

    doc.saveAndClose();

    // Move to target folder
    const file   = DriveApp.getFileById(doc.getId());
    const folder = DriveApp.getFolderById(folderId);
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file); // remove from root

    Logger.log('Anschreiben created: ' + doc.getUrl());
    return doc.getUrl();

  } catch (err) {
    Logger.log('Google Doc creation error: ' + err.message);
    return null;
  }
}

/**
 * Builds the cover letter prompt in German.
 */
function buildPrompt(job) {
  const company  = job.company       || 'das Unternehmen';
  const title    = job.job_title     || 'die ausgeschriebene Stelle';
  const location = job.location      || '';
  const contact  = job.employer_name || '';
  const summary  = job.summary       || '';

  const locationLine = location ? ' in ' + location : '';
  const salutation   = contact
    ? 'Sehr geehrte/r ' + contact + ','
    : 'Sehr geehrte Damen und Herren,';

  return `Schreibe ein professionelles Bewerbungsanschreiben auf Deutsch.

Stelle: ${title}${locationLine}
Unternehmen: ${company}
${summary ? 'Stellenbeschreibung: ' + summary : ''}

Kandidatenprofil:
- Schwerpunkt: KI-Automatisierung, Workflow-Engineering (n8n, Make.com, Zapier)
- Technisch: Python, JavaScript, REST APIs, LLM-Integration (Claude, GPT, OpenRouter)
- Sonstige Kenntnisse: Docker, PostgreSQL, Google Cloud, Telegram Bots, RAG-Pipelines
- Sprachen: Russisch (Muttersprache), Deutsch (~C1), Englisch (B2)
- Keine offizielle Berufserfahrung — dafür starkes Projektportfolio

Format des Anschreibens:
${salutation}

[Einleitung — warum diese Stelle interessant ist]

[Hauptteil — relevante Fähigkeiten konkret auf die Stelle bezogen, 2-3 Absätze]

[Schluss — Einladung zum Gespräch, Danke]

Mit freundlichen Grüßen,
[Name]

Stil: direkt, professionell, selbstbewusst. Keine Floskeln wie "Hiermit bewerbe ich mich".
Länge: 3-4 Absätze, max 350 Wörter. Nur den Brief ausgeben, kein Kommentar.`;
}

// ── Manual test ──────────────────────────────────────────────
// Run this from the Script Editor to test without the Sheet
function testGenerateAnschreiben() {
  const url = generateAnschreiben({
    company:       'Nebula AI GmbH',
    job_title:     'AI Workflow Engineer',
    location:      'Remote',
    employer_name: 'Anna Schmidt',
    summary:       'n8n, Python, LLM-Integration, REST APIs, 50-65k EUR, vollständig remote'
  });
  Logger.log('Result URL: ' + url);
}

// ============================================================
// MASSENANSCHREIBEN — Шаблонный подход для Massenversand
// ============================================================
// Логика:
//   - Базовый текст письма фиксированный (шаблон ниже)
//   - LLM генерирует ТОЛЬКО одну фразу: [FIRMA_GRUND_1_SATZ]
//   - Плейсхолдеры [FIRMA_NAME], [FIRMA_ORT], [STELLE] заполняются
//     напрямую из данных вакансии — без LLM
//
// Преимущества vs generateAnschreiben():
//   - Тело письма одинаковое → меньше ошибок, стабильный стиль
//   - LLM тратит ~100 токенов вместо 1500
//   - Можно прогнать 50 вакансий за минуту
// ============================================================

const MASSEN_TEMPLATE = `Kirill Brüggemann · Berlin
ogi-ogi@mail.de · github.com/KiBrueg · linkedin.com/in/ki-brueg-2520033bb

Berlin, {{DATUM}}

{{FIRMA_NAME}}
{{FIRMA_ORT}}

Betreff: Bewerbung als {{STELLE}} (m/w/d)

Sehr geehrte Damen und Herren,

ich bin Automation Engineer aus Berlin mit Schwerpunkt auf KI-gestützten Systemen, LLM-Integration und Backend-Entwicklung. Ich bewerbe mich bei {{FIRMA_NAME}}, weil {{FIRMA_GRUND}}.  Das Arbeitsformat ist für mich flexibel — Praktikum, Teilzeit, Vollzeit oder freiberuflich; entscheidend ist das Problem, das wir gemeinsam lösen.

Was ich mitbringe: Ich baue produktionsreife Systeme in Python, die wirklich laufen. Mein Referenzprojekt JobRadar ist eine vollautomatisierte Multi-Source-Pipeline mit LLM-Parser, PostgreSQL-Backend, HMAC-Webhook-Auth und Prompt Injection Detection — deployed auf eigenem VPS mit Docker. Daneben habe ich einen Crypto Intel Agent mit Multi-Agenten-Architektur (Council of Advisors), Vektorsuche via pgvector und vollständiger pytest-Test-Suite entwickelt. LLM-APIs (Claude, OpenAI, open-source über OpenRouter), REST-Integrationen, n8n-Workflows, Telegram-Bots — alles aus eigener Initiative, ohne Team, ohne Deadline-Druck von außen.

Ich bin Berliner, spreche Deutsch auf Verhandlungsniveau (C1), Englisch (B2) und Russisch (Muttersprache). Remote bevorzugt, Hybrid oder vor Ort nach Absprache möglich. Verfügbar kurzfristig.

Wenn Sie ein konkretes Problem haben, das Automatisierung, KI oder Backend-Entwicklung lösen kann — ich höre gerne zu.

Mit freundlichen Grüßen,
Kirill Brüggemann`;

/**
 * Генерирует персонализированное Massenanschreiben.
 * LLM заполняет только [FIRMA_GRUND] — одну фразу про компанию.
 *
 * @param {Object} job { company, city, job_title, summary }
 * @returns {string|null} URL Google Doc или null при ошибке
 */
function generateMassenAnschreiben(job) {
  const props    = PropertiesService.getScriptProperties();
  const apiKey   = props.getProperty('OPENROUTER_KEY');
  const folderId = props.getProperty('LETTERS_FOLDER_ID');

  if (!apiKey || !folderId) {
    Logger.log('Missing Script Properties: OPENROUTER_KEY or LETTERS_FOLDER_ID');
    return null;
  }

  const company   = job.company   || 'das Unternehmen';
  const city      = job.city      || 'Berlin';
  const title     = job.job_title || 'die Stelle';
  const summary   = job.summary   || '';

  // ── 1. LLM generiert NUR eine Begründungs-Phrase ────────────
  let grund = '';
  try {
    const prompt = `Schreibe GENAU EINEN kurzen deutschen Satz (max. 15 Wörter), warum sich ein AI/Automation Engineer bei diesem Unternehmen bewirbt.

Unternehmen: ${company}
Standort: ${city}
Stelle: ${title}
${summary ? 'Kurzbeschreibung: ' + summary : ''}

Nur den Satz ausgeben, kein Punkt am Ende, keine Anführungszeichen.
Beispiel: "Ihre Arbeit an LLM-basierten Pipelines für den öffentlichen Sektor mich direkt anspricht"`;

    const response = UrlFetchApp.fetch(
      'https://openrouter.ai/api/v1/chat/completions',
      {
        method:             'POST',
        muteHttpExceptions: true,
        headers: {
          'Authorization': 'Bearer ' + apiKey,
          'Content-Type':  'application/json',
          'HTTP-Referer':  'https://jobradar.app',
          'X-Title':       'JobRadar Massenanschreiben'
        },
        payload: JSON.stringify({
          model:      'qwen/qwen3-30b-a3b-instruct-2507',
          max_tokens: 80,
          messages:   [{ role: 'user', content: prompt }]
        })
      }
    );

    if (response.getResponseCode() === 200) {
      let raw = JSON.parse(response.getContentText()).choices[0].message.content || '';
      raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
      raw = raw.replace(/^["']|["']$/g, '').trim(); // strip quotes
      grund = raw;
    }
  } catch (err) {
    Logger.log('LLM error (non-fatal): ' + err.message);
  }

  // Fallback если LLM не ответил
  if (!grund) {
    grund = 'Ihre Projekte im Bereich KI-Automatisierung mich direkt ansprechen';
  }

  // ── 2. Platzhalter ersetzen ──────────────────────────────────
  const datum = Utilities.formatDate(new Date(), 'Europe/Berlin', 'MMMM yyyy');
  const letterText = MASSEN_TEMPLATE
    .replace(/{{DATUM}}/g,       datum)
    .replace(/{{FIRMA_NAME}}/g,  company)
    .replace(/{{FIRMA_ORT}}/g,   city)
    .replace(/{{STELLE}}/g,      title)
    .replace(/{{FIRMA_GRUND}}/g, grund);

  // ── 3. Google Doc erstellen ──────────────────────────────────
  try {
    const today   = Utilities.formatDate(new Date(), 'Europe/Berlin', 'yyyy-MM-dd');
    const docName = 'Anschreiben (Massen) — ' + company + ' — ' + today;

    const doc  = DocumentApp.create(docName);
    const body = doc.getBody();
    body.clear();

    letterText.split(/\n\n+/).forEach(function(para, i) {
      if (i === 0) {
        body.editAsText().setText(para.trim());
      } else {
        body.appendParagraph(para.trim());
      }
    });

    doc.saveAndClose();

    const file   = DriveApp.getFileById(doc.getId());
    const folder = DriveApp.getFolderById(folderId);
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file);

    Logger.log('Massenanschreiben created: ' + doc.getUrl());
    return doc.getUrl();

  } catch (err) {
    Logger.log('Google Doc error: ' + err.message);
    return null;
  }
}

/**
 * Пакетная генерация: читает вакансии из активного Sheet,
 * генерирует письмо для каждой строки где колонка "Anschreiben_URL" пустая.
 *
 * Колонки Sheet (A–F):
 *   A: Unternehmen | B: Stadt | C: Stelle | D: Zusammenfassung | E: Status | F: Anschreiben_URL
 */
function batchGenerateMassenAnschreiben() {
  const sheet  = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data   = sheet.getDataRange().getValues();

  // Skip header row
  for (let i = 1; i < data.length; i++) {
    const [company, city, title, summary, status, existingUrl] = data[i];

    if (!company || existingUrl) continue; // skip empty or already generated

    Logger.log('Generating for: ' + company);

    const url = generateMassenAnschreiben({ company, city, job_title: title, summary });

    if (url) {
      sheet.getRange(i + 1, 6).setValue(url);   // col F: Anschreiben_URL
      sheet.getRange(i + 1, 5).setValue('Generiert'); // col E: Status
    }

    Utilities.sleep(2000); // rate limiting
  }

  Logger.log('Batch done.');
}

// ── Test ─────────────────────────────────────────────────────
function testMassenAnschreiben() {
  const url = generateMassenAnschreiben({
    company:   'TechStart GmbH',
    city:      'Berlin',
    job_title: 'Junior AI Engineer',
    summary:   'Python, LLM, n8n, Automatisierung, Startup-Umfeld'
  });
  Logger.log('Result: ' + url);
}
