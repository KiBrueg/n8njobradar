// ============================================================
// JobRadar — Google Sheets Writer v2
// POST endpoint: receives {jobs: [...]} from n8n Flow 6
// Columns: Quelle | Score | Firma | Stelle | Level | Ort | Stage | Anschreiben | Ansprechpartner | Zusammenfassung | Link | Datum
// ============================================================

function doPost(e) {
  try {
    const data    = JSON.parse(e.postData.contents);
    const jobs    = data.jobs || [];
    const SHEET_ID = '1Cg8f-iJ49TB6pd_Qc-2crRoUrYvbfIZExoPrkhy4ZMk';
    const ss      = SpreadsheetApp.openById(SHEET_ID);
    const sheet   = ss.getSheetByName('Tabellenblatt1') || ss.getActiveSheet();

    const HEADERS = [
      'Quelle', 'Score', 'Firma', 'Stelle', 'Level',
      'Ort / Modus', 'Stage', 'Anschreiben', 'Ansprechpartner',
      'Zusammenfassung', 'Link', 'Datum'
    ];
    const NCOLS = HEADERS.length;

    // --- Clear old data (keep row 1) ---
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.getRange(2, 1, lastRow - 1, NCOLS).clearContent().clearFormat();
    }

    // --- Headers ---
    const hdrRange = sheet.getRange(1, 1, 1, NCOLS);
    hdrRange.setValues([HEADERS]);
    hdrRange.setFontWeight('bold')
            .setBackground('#2c3e50')
            .setFontColor('#ffffff')
            .setHorizontalAlignment('center');

    // --- Freeze header row ---
    sheet.setFrozenRows(1);

    if (jobs.length === 0) {
      return ok(0);
    }

    // ---- Helper functions ----

    function sourceEmoji(site) {
      const s = (site || '').toLowerCase();
      if (s.includes('xing'))             return '🔷 XING';
      if (s.includes('linkedin'))         return '💼 LinkedIn';
      if (s.includes('freelancermap'))    return '🗺 FreelancerMap';
      if (s.includes('gulp'))             return '🌊 GULP';
      if (s.includes('malt'))             return '🍺 Malt';
      if (s.includes('freelance.de'))     return '🔧 Freelance.de';
      if (s.includes('berlinstartupjobs'))return '🚀 BerlinStartupJobs';
      if (s.includes('indeed'))           return '🔍 Indeed';
      if (s.includes('greenhouse'))       return '🌿 Greenhouse';
      if (s.includes('lever'))            return '⚙️ Lever';
      if (s.includes('arbeitnow'))        return '💡 Arbeitnow';
      if (s.includes('remotive'))         return '🌐 Remotive';
      if (s.includes('weworkremotely'))   return '💻 WeWorkRemotely';
      if (s.includes('devjobs'))          return '🛠 DevJobs';
      if (s.includes('stepstone'))        return '📋 StepStone';
      if (s.includes('jobrapido'))        return '📡 Jobrapido';
      if (s.includes('jooble'))           return '🔎 Jooble';
      if (s === 'manual')                 return '✍️ Manual';
      return '🌐 ' + (site || 'Unbekannt');
    }

    function scoreBar(n) {
      n = Math.max(0, Math.min(100, parseInt(n) || 0));
      const filled = Math.round(n / 10);
      return '█'.repeat(filled) + '░'.repeat(10 - filled) + '  ' + n;
    }

    function stageLabel(s) {
      return {
        'discovered':  '🔍 Entdeckt',
        'applied':     '📬 Beworben',
        'screening':   '🔎 Sichtung',
        'interview':   '🤝 Interview',
        'test_task':   '📝 Testaufgabe',
        'offer':       '🎉 Angebot',
        'rejected':    '❌ Abgelehnt',
        'withdrawn':   '🚫 Zurückgezogen'
      }[s] || (s || '');
    }

    function seniorityLabel(s) {
      return {
        'intern':  '⚪ Intern',
        'junior':  '🟢 Junior',
        'middle':  '🟡 Mid',
        'senior':  '🔴 Senior',
        'lead':    '🔴 Lead',
        'principal':'🔴 Principal'
      }[s] || (s || '');
    }

    function locStr(job) {
      const parts = [job.location, job.work_mode ? job.work_mode.replace(/_/g,' ') : null].filter(Boolean);
      return parts.join(' / ');
    }

    function dateStr(d) {
      return d ? String(d).substring(0, 10) : '';
    }

    // ---- Build rows ----
    const values   = [];
    const formulas = [];   // for Link column only (col 11)

    jobs.forEach(function(job) {
      const score = parseInt(job.relevance_score) || 0;
      const url   = (job.source_url || '').replace(/"/g, '');

      values.push([
        sourceEmoji(job.source_site),          // 1 Quelle
        scoreBar(score),                        // 2 Score
        job.company        || '',               // 3 Firma
        job.job_title      || '',               // 4 Stelle
        seniorityLabel(job.seniority),          // 5 Level
        locStr(job),                            // 6 Ort / Modus
        stageLabel(job.current_stage),          // 7 Stage
        '',                                     // 8 Anschreiben (manual)
        job.employer_name  || '',               // 9 Ansprechpartner
        job.summary        || '',               // 10 Zusammenfassung
        '',                                     // 11 Link (set as formula below)
        dateStr(job.created_at)                 // 12 Datum
      ]);

      formulas.push(url
        ? '=HYPERLINK("' + url + '","🔗 Öffnen")'
        : '');
    });

    // --- Write values ---
    const dataRange = sheet.getRange(2, 1, values.length, NCOLS);
    dataRange.setValues(values);

    // --- Write link formulas (col 11) ---
    const linkRange = sheet.getRange(2, 11, formulas.length, 1);
    linkRange.setFormulas(formulas.map(function(f){ return [f]; }));
    linkRange.setHorizontalAlignment('center');

    // --- Row color by score ---
    jobs.forEach(function(job, i) {
      const score = parseInt(job.relevance_score) || 0;
      const row   = sheet.getRange(i + 2, 1, 1, NCOLS);
      if (score >= 80)      row.setBackground('#d4edda');  // green
      else if (score >= 50) row.setBackground('#fff3cd');  // yellow
      else                  row.setBackground('#f8f9fa');  // light grey
    });

    // --- Score bar: bold + center ---
    sheet.getRange(2, 2, values.length, 1)
         .setFontFamily('Courier New')
         .setHorizontalAlignment('left');

    // --- Zusammenfassung: wrap text ---
    sheet.getRange(2, 10, values.length, 1).setWrap(true);

    // --- Column widths ---
    sheet.setColumnWidth(1,  160);  // Quelle
    sheet.setColumnWidth(2,  160);  // Score
    sheet.setColumnWidth(3,  160);  // Firma
    sheet.setColumnWidth(4,  220);  // Stelle
    sheet.setColumnWidth(5,  100);  // Level
    sheet.setColumnWidth(6,  160);  // Ort
    sheet.setColumnWidth(7,  130);  // Stage
    sheet.setColumnWidth(8,  120);  // Anschreiben
    sheet.setColumnWidth(9,  140);  // Ansprechpartner
    sheet.setColumnWidth(10, 380);  // Zusammenfassung
    sheet.setColumnWidth(11,  90);  // Link
    sheet.setColumnWidth(12, 100);  // Datum

    return ok(values.length);

  } catch(err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function ok(n) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', written: n }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---- Manual test (run from Apps Script editor) ----
function testWrite() {
  doPost({
    postData: {
      contents: JSON.stringify({
        jobs: [
          {
            relevance_score: 92,
            source_site: 'XING',
            company: 'Nebula AI GmbH',
            job_title: 'AI Workflow Engineer',
            seniority: 'middle',
            location: 'Berlin, Germany',
            work_mode: 'remote',
            current_stage: 'discovered',
            summary: 'Тестовая запись. Позиция AI Workflow Engineer, полностью удалённо, 60–70k EUR.',
            source_url: 'https://www.xing.com/jobs/test',
            created_at: '2026-06-14T10:00:00Z'
          },
          {
            relevance_score: 65,
            source_site: 'freelancermap',
            company: 'TechSolutions UG',
            job_title: 'Python Automation Developer',
            seniority: 'middle',
            location: 'Remote',
            work_mode: 'remote',
            current_stage: 'applied',
            summary: 'Фриланс-проект по автоматизации на Python и n8n.',
            source_url: 'https://www.freelancermap.de/projekt/test',
            created_at: '2026-06-14T09:00:00Z'
          }
        ]
      })
    }
  });
}
