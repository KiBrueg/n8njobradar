# ============================================================
# update-exclusion-list.ps1
# Читает статусы вакансий из Postgres на VPS и обновляет
# секцию Ausschlussliste в spec/job-search-prompt.md
#
# Запуск: .\scripts\update-exclusion-list.ps1
# ============================================================

$VPS_USER = "kirill"
$VPS_HOST = $env:VPS_HOST
$SSH_KEY  = "$env:USERPROFILE\.ssh\id_ed25519"
$PROMPT_FILE = "$PSScriptRoot\..\spec\job-search-prompt.md"

Write-Host "Подключаюсь к VPS и читаю базу jobradar..." -ForegroundColor Cyan

# SQL: берём company_name + current_stage для всех вакансий
$SQL = @"
SELECT
  company_name,
  current_stage::text AS stage,
  job_title
FROM jobs
ORDER BY current_stage, company_name;
"@

# Запускаем через SSH
$raw = ssh -i $SSH_KEY "${VPS_USER}@${VPS_HOST}" "psql -U hub -d jobradar -t -A -F'|' -c `"$SQL`"" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка SSH: $raw" -ForegroundColor Red
    exit 1
}

# Парсим вывод
$abgelehnt   = @()
$beworben    = @()
$screening   = @()
$interview   = @()
$angebot     = @()

foreach ($line in $raw -split "`n") {
    $line = $line.Trim()
    if (-not $line -or $line -match "^--" -or $line -match "^\(") { continue }
    $parts = $line -split "\|"
    if ($parts.Count -lt 2) { continue }
    $company = $parts[0].Trim()
    $stage   = $parts[1].Trim()
    $title   = if ($parts.Count -ge 3) { $parts[2].Trim() } else { "" }
    $entry   = if ($title) { "$company ($title)" } else { $company }

    switch ($stage) {
        "rejected"    { $abgelehnt  += $entry }
        "applied"     { $beworben   += $entry }
        "screening"   { $screening  += $entry }
        "interview"   { $interview  += $entry }
        "offer"       { $angebot    += $entry }
    }
}

# Форматируем секцию
$date = Get-Date -Format "yyyy-MM-dd"

$section = @"
### ❌ Ausschlussliste
- **Abgelehnt:** $($abgelehnt -join ", ")
- **Bereits beworben:** $($beworben -join ", ")
- **Im Prozess (Screening):** $($screening -join ", ")
- **Im Prozess (Interview):** $($interview -join ", ")
- Kein SAP (außer Remote + Einsteiger OK), kein Hybrid/Büro/Umzug, kein Java/.NET/PHP als Festanstellung-Pflicht

*Letzte Aktualisierung: $date | Flow 7: 51 Queries | Flow 2: 18 Scrape-Targets | Flow 2b: 23 Career Pages*
"@

# Читаем файл и заменяем секцию
$content = Get-Content $PROMPT_FILE -Raw -Encoding UTF8

# Заменяем от "### ❌ Ausschlussliste" до конца файла
$newContent = $content -replace "(?s)### ❌ Ausschlussliste.*$", $section.TrimEnd()

Set-Content $PROMPT_FILE -Value $newContent -Encoding UTF8 -NoNewline

Write-Host ""
Write-Host "✅ Готово! Обновлён $PROMPT_FILE" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Статистика:" -ForegroundColor Yellow
Write-Host "  Abgelehnt  : $($abgelehnt.Count)"
Write-Host "  Beworben   : $($beworben.Count)"
Write-Host "  Screening  : $($screening.Count)"
Write-Host "  Interview  : $($interview.Count)"
Write-Host "  Angebot    : $($angebot.Count)"
Write-Host ""
Write-Host "Abgelehnt: $($abgelehnt -join ', ')" -ForegroundColor DarkGray
Write-Host "Beworben:  $($beworben -join ', ')" -ForegroundColor DarkGray
