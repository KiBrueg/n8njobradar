// ============================================================
// JobRadar — Google Sheets Writer v3
// POST endpoint: receives { jobs: [...] } from n8n Flow 6
// Columns: Score | Quelle | Firma | Stelle | Modus | Stage | Zusammenfassung | Link | Datum
// ============================================================

var SHEET_ID = '1Cg8f-iJ49TB6pd_Qc-2crRoUrYvbfIZExoPrkhy4ZMk';

var HEADERS = [
  'Score', 'Quelle', 'Firma', 'Stelle', 'Modus', 'Stage', 'Zusammenfassung', 'Link', 'Datum'
];

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var jobs  = data.jobs || [];

    var ss    = SpreadsheetApp.openById(SHEET_ID);
    var sheet = ss.getSheetByName('Tabellenblatt1') || ss.getSheets()[0];
    var NCOLS = HEADERS.length;

    // --- Полная очистка листа ---
    sheet.clearContents();
    sheet.clearFormats();

    // --- Заголовки ---
    var hdr = sheet.getRange(1, 1, 1, NCOLS);
    hdr.setValues([HEADERS]);
    hdr.setFontWeight('bold')
       .setBackground('#1a1a2e')
       .setFontColor('#e0e0e0')
       .setHorizontalAlignment('center')
       .setFontSize(11);
    sheet.setFrozenRows(1);

    if (jobs.length === 0) {
      sheet.getRange(2, 1).setValue('— keine Daten —');
      return ok(0);
    }

    // ---- Вспомогательные функции ----

    function scoreBar(n) {
      n = Math.max(0, Math.min(100, parseInt(n) || 0));
      var filled = Math.round(n / 10);
      return String(n) + ' ' + '█'.repeat(filled) + '░'.repeat(10 - filled);
    }

    function modeLabel(m) {
      var map = { remote: '🌐 Remote', hybrid: '🔀 Hybrid', onsite: '🏢 Onsite' };
      return map[(m || '').toLowerCase()] || (m || '—');
    }

    function stageLabel(s) {
      var map = {
        discovered:  '🔍 Entdeckt',
        applied:     '📬 Beworben',
        screening:   '🔎 Sichtung',
        interview:   '🤝 Interview',
        test_task:   '📝 Testaufgabe',
        offer:       '🎉 Angebot',
        rejected:    '❌ Abgelehnt',
        withdrawn:   '🚫 Zurückgez.'
      };
      return map[s] || (s || '—');
    }

    function sourceLabel(url) {
      var u = (url || '').toLowerCase();
      if (u.indexOf('xing.com') >= 0)           return 'XING';
      if (u.indexOf('linkedin.com') >= 0)        return 'LinkedIn';
      if (u.indexOf('freelancermap') >= 0)       return 'FreelancerMap';
      if (u.indexOf('gulp.de') >= 0)             return 'GULP';
      if (u.indexOf('malt.de') >= 0)             return 'Malt';
      if (u.indexOf('freelance.de') >= 0)        return 'Freelance.de';
      if (u.indexOf('berlinstartupjobs') >= 0)   return 'BSJ';
      if (u.indexOf('indeed.') >= 0)             return 'Indeed';
      if (u.indexOf('arbeitnow') >= 0)           return 'Arbeitnow';
      if (u.indexOf('remotive') >= 0)            return 'Remotive';
      if (u.indexOf('greenhouse.io') >= 0)       return 'Greenhouse';
      if (u.indexOf('lever.co') >= 0)            return 'Lever';
      if (u.indexOf('gewerbe-daily') >= 0)       return 'Gewerbe';
      return 'Web';
    }

    function dateStr(d) {
      return d ? String(d).substring(0, 10) : '';
    }

    // ---- Строки данных ----
    var values   = [];
    var formulas = [];

    jobs.forEach(function(job) {
      var score = parseInt(job.relevance_score) || 0;
      var url   = (job.source_url || '').replace(/"/g, '');

      values.push([
        scoreBar(score),                  // 1 Score
        sourceLabel(job.source_url),      // 2 Quelle
        job.company     || '—',           // 3 Firma
        job.job_title   || '—',           // 4 Stelle
        modeLabel(job.work_mode),         // 5 Modus
        stageLabel(job.current_stage),    // 6 Stage
        job.summary     || '',            // 7 Zusammenfassung
        '',                               // 8 Link (формула ниже)
        dateStr(job.created_at)           // 9 Datum
      ]);

      formulas.push(url ? '=HYPERLINK("' + url + '","Link")' : '');
    });

    // --- Записываем данные ---
    var dataRange = sheet.getRange(2, 1, values.length, NCOLS);
    dataRange.setValues(values);

    // --- Формулы ссылок (col 8) ---
    var linkRange = sheet.getRange(2, 8, formulas.length, 1);
    linkRange.setFormulas(formulas.map(function(f){ return [f]; }));
    linkRange.setHorizontalAlignment('center');

    // --- Цвет строк по скору ---
    jobs.forEach(function(job, i) {
      var score = parseInt(job.relevance_score) || 0;
      var row   = sheet.getRange(i + 2, 1, 1, NCOLS);
      if (score >= 80)      row.setBackground('#d4edda');  // зелёный
      else if (score >= 50) row.setBackground('#fff3cd');  // жёлтый
      else                  row.setBackground('#f8f9fa');  // серый
    });

    // --- Score: моноширинный ---
    sheet.getRange(2, 1, values.length, 1)
         .setFontFamily('Courier New')
         .setFontSize(10);

    // --- Zusammenfassung: перенос текста ---
    sheet.getRange(2, 7, values.length, 1).setWrap(true);

    // --- Ширина колонок ---
    sheet.setColumnWidth(1, 140);  // Score
    sheet.setColumnWidth(2, 130);  // Quelle
    sheet.setColumnWidth(3, 160);  // Firma
    sheet.setColumnWidth(4, 230);  // Stelle
    sheet.setColumnWidth(5, 110);  // Modus
    sheet.setColumnWidth(6, 120);  // Stage
    sheet.setColumnWidth(7, 420);  // Zusammenfassung
    sheet.setColumnWidth(8,  70);  // Link
    sheet.setColumnWidth(9, 100);  // Datum

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

// ---- Тест из редактора Apps Script: Run → testWrite ----
function testWrite() {
  doPost({
    postData: {
      contents: JSON.stringify({
        jobs: [
          {
            relevance_score: 87,
            source_url: 'https://www.xing.com/jobs/test-1',
            company: 'Nebula AI GmbH',
            job_title: 'AI Workflow Engineer',
            work_mode: 'remote',
            current_stage: 'discovered',
            summary: 'Vollständig remote. Python, n8n, LLM-Integration. Score 87.',
            created_at: '2026-06-15'
          },
          {
            relevance_score: 62,
            source_url: 'https://www.freelancermap.de/projekt/test-2',
            company: 'TechSolutions UG',
            job_title: 'Python Automation Developer',
            work_mode: 'hybrid',
            current_stage: 'applied',
            summary: 'Hybrid, München. Python, REST APIs. Score 62.',
            created_at: '2026-06-15'
          },
          {
            relevance_score: 20,
            source_url: 'https://www.freelancermap.de/projekt/payroll',
            company: 'PAR GmbH',
            job_title: 'Payroll Specialist',
            work_mode: 'onsite',
            current_stage: 'discovered',
            summary: 'Vor Ort, Frankfurt. SAP HCM. Score 20.',
            created_at: '2026-06-15'
          }
        ]
      })
    }
  });
}
