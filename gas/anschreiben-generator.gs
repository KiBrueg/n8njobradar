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
