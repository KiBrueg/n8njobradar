<#
.SYNOPSIS
    Erstellt die Ordnerstruktur für Handwerk-Dokumentenablage in SharePoint Online.

.DESCRIPTION
    Nutzt Microsoft Graph API (keine PnP PowerShell nötig) um SharePoint-Ordner
    anzulegen und Versionierung zu aktivieren. Führt alle Operationen idempotent aus
    (bereits existierende Ordner werden übersprungen).

.PREREQUISITES
    - PowerShell 5.1+ oder PowerShell 7+
    - Microsoft 365 Konto mit SharePoint-Admin-Berechtigung
    - Microsoft.Graph PowerShell Modul: Install-Module Microsoft.Graph -Scope CurrentUser

.USAGE
    1. Variablen unten anpassen (TenantName, SiteName)
    2. In PowerShell ausführen: .\09-sharepoint-setup.ps1
    3. Browser öffnet sich für Microsoft Login (OAuth2)
    4. Nach Fertigstellung: Site-ID und Library-ID werden ausgegeben
       → Diese IDs in Make.com Custom Variables eintragen!

.OUTPUTS
    - SharePoint Ordnerstruktur unter /HandwerkDokumente/
    - Site-ID, Library-ID, Drive-ID (für Make.com)
    - Versionierung aktiviert für alle Dokumentenbibliotheken
#>

#Requires -Version 5.1

# ============================================================
# KONFIGURATION — Anpassen!
# ============================================================

$TenantName    = "IHRE-FIRMA"          # z.B. "mustermann" wenn mustermann.sharepoint.com
$SiteName      = "HandwerkDokumente"   # SharePoint-Site-Name (wird angelegt wenn nicht vorhanden)
$LibraryName   = "Dokumente"           # Standard-Dokumentenbibliothek

# ============================================================
# ORDNERSTRUKTUR — nicht ändern außer wenn angepasst werden soll
# ============================================================

$Folders = @(
    "HandwerkDokumente",
    "HandwerkDokumente/Eingangsrechnungen",
    "HandwerkDokumente/Eingangsrechnungen/2026",
    "HandwerkDokumente/Eingangsrechnungen/2026/01_Januar",
    "HandwerkDokumente/Eingangsrechnungen/2026/02_Februar",
    "HandwerkDokumente/Eingangsrechnungen/2026/03_Maerz",
    "HandwerkDokumente/Eingangsrechnungen/2026/04_April",
    "HandwerkDokumente/Eingangsrechnungen/2026/05_Mai",
    "HandwerkDokumente/Eingangsrechnungen/2026/06_Juni",
    "HandwerkDokumente/Eingangsrechnungen/2026/07_Juli",
    "HandwerkDokumente/Eingangsrechnungen/2026/08_August",
    "HandwerkDokumente/Eingangsrechnungen/2026/09_September",
    "HandwerkDokumente/Eingangsrechnungen/2026/10_Oktober",
    "HandwerkDokumente/Eingangsrechnungen/2026/11_November",
    "HandwerkDokumente/Eingangsrechnungen/2026/12_Dezember",
    "HandwerkDokumente/Ausgangsrechnungen",
    "HandwerkDokumente/Ausgangsrechnungen/2026",
    "HandwerkDokumente/Angebote",
    "HandwerkDokumente/Angebote/2026",
    "HandwerkDokumente/Lieferscheine",
    "HandwerkDokumente/Lieferscheine/2026",
    "HandwerkDokumente/Vertraege",
    "HandwerkDokumente/Vertraege/2026",
    "HandwerkDokumente/Bauplaene",
    "HandwerkDokumente/Bauplaene/2026",
    "HandwerkDokumente/Projekte",
    "HandwerkDokumente/Projekte/_Vorlage",
    "HandwerkDokumente/Projekte/_Vorlage/Lieferscheine",
    "HandwerkDokumente/Projekte/_Vorlage/Plaene",
    "HandwerkDokumente/Projekte/_Vorlage/Korrespondenz",
    "HandwerkDokumente/Eingang-Manuell-Pruefen",
    "HandwerkDokumente/Archiv"
)

# ============================================================
# SCRIPT — Nicht ändern ohne Verständnis
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message, [string]$Color = "Cyan")
    Write-Host "`n[$( Get-Date -Format 'HH:mm:ss' )] $Message" -ForegroundColor $Color
}

function Write-OK   { param([string]$msg) Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-Skip { param([string]$msg) Write-Host "  ⏭  $msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$msg) Write-Host "  ❌ $msg" -ForegroundColor Red }

# 1. Microsoft.Graph Modul prüfen
Write-Step "Prüfe Microsoft.Graph Modul..."
if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Sites)) {
    Write-Host "Installiere Microsoft.Graph (dauert ca. 2-3 Minuten)..." -ForegroundColor Yellow
    Install-Module Microsoft.Graph -Scope CurrentUser -Force -AllowClobber
}
Write-OK "Microsoft.Graph verfügbar"

# 2. Verbinden
Write-Step "Verbinde mit Microsoft 365..."
Write-Host "  Browser öffnet sich für Anmeldung..." -ForegroundColor Yellow
Connect-MgGraph -Scopes "Sites.ReadWrite.All", "Files.ReadWrite.All" -ErrorAction Stop
Write-OK "Verbunden"

# 3. Site suchen oder anlegen
Write-Step "Suche SharePoint Site '$SiteName'..."
$SiteUrl = "https://$TenantName.sharepoint.com/sites/$SiteName"

try {
    $Site = Get-MgSite -SiteId "$TenantName.sharepoint.com:/sites/$SiteName" -ErrorAction Stop
    Write-OK "Site gefunden: $($Site.Id)"
} catch {
    Write-Host "  Site nicht gefunden — Hinweis: Sites können nicht per Script angelegt werden." -ForegroundColor Yellow
    Write-Host "  Bitte manuell anlegen: admin.microsoft.com → SharePoint Admin → Aktive Sites → + Erstellen" -ForegroundColor Yellow
    Write-Host "  Danach Script neu ausführen." -ForegroundColor Yellow
    exit 1
}

$SiteId = $Site.Id

# 4. Drive (Dokumentenbibliothek) holen
Write-Step "Hole Dokumentenbibliothek..."
$Drives = Get-MgSiteDrive -SiteId $SiteId
$Drive = $Drives | Where-Object { $_.Name -eq $LibraryName } | Select-Object -First 1

if (-not $Drive) {
    $Drive = $Drives | Select-Object -First 1
    Write-Skip "Bibliothek '$LibraryName' nicht gefunden — nutze erste verfügbare: $($Drive.Name)"
} else {
    Write-OK "Bibliothek gefunden: $($Drive.Name) (ID: $($Drive.Id))"
}

$DriveId = $Drive.Id

# 5. Ordnerstruktur anlegen
Write-Step "Lege Ordnerstruktur an ($($Folders.Count) Ordner)..."

foreach ($FolderPath in $Folders) {
    $PathParts = $FolderPath -split "/"
    $FolderName = $PathParts[-1]

    if ($PathParts.Count -eq 1) {
        # Root-Ordner
        $ParentPath = "root"
    } else {
        $ParentPath = "root:/" + ($PathParts[0..($PathParts.Count - 2)] -join "/") + ":"
    }

    try {
        # Prüfen ob Ordner schon existiert
        if ($PathParts.Count -eq 1) {
            $ExistingItems = Get-MgDriveRootChild -DriveId $DriveId -ErrorAction SilentlyContinue
        } else {
            $ParentFolder = "root:/" + ($PathParts[0..($PathParts.Count - 2)] -join "/") + ":"
            $ExistingItems = Get-MgDriveItemChild -DriveId $DriveId -DriveItemId $ParentFolder -ErrorAction SilentlyContinue
        }

        $Exists = $ExistingItems | Where-Object { $_.Name -eq $FolderName } | Select-Object -First 1

        if ($Exists) {
            Write-Skip "Existiert bereits: $FolderPath"
            continue
        }
    } catch {
        # Fehler beim Prüfen ignorieren — versuchen anzulegen
    }

    try {
        $NewFolder = @{
            Name   = $FolderName
            Folder = @{}
            "@microsoft.graph.conflictBehavior" = "fail"
        }

        if ($PathParts.Count -eq 1) {
            New-MgDriveRootFolder -DriveId $DriveId -BodyParameter $NewFolder -ErrorAction Stop | Out-Null
        } else {
            $ParentItemPath = "root:/" + ($PathParts[0..($PathParts.Count - 2)] -join "/") + ":"
            New-MgDriveItemFolder -DriveId $DriveId -DriveItemId $ParentItemPath -BodyParameter $NewFolder -ErrorAction Stop | Out-Null
        }

        Write-OK "Erstellt: $FolderPath"
    } catch {
        if ($_.Exception.Message -like "*nameAlreadyExists*") {
            Write-Skip "Existiert bereits: $FolderPath"
        } else {
            Write-Err "Fehler bei $FolderPath : $($_.Exception.Message)"
        }
    }
}

# 6. Versionierung aktivieren
Write-Step "Aktiviere Versionierung für Dokumentenbibliothek..."

try {
    $LibraryUpdate = @{
        List = @{
            EnableVersioning     = $true
            MajorVersionLimit    = 50
            EnableMinorVersions  = $false
        }
    }

    Update-MgSiteList -SiteId $SiteId -ListId $Drive.List.Id -BodyParameter $LibraryUpdate -ErrorAction Stop
    Write-OK "Versionierung aktiviert (50 Versionen)"
} catch {
    Write-Skip "Versionierung konnte nicht per API gesetzt werden — bitte manuell: Library Settings → Versioning Settings → Major versions: 50"
}

# 7. IDs ausgeben (für Make.com)
Write-Step "FERTIG! IDs für Make.com:" "Green"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  DIESE WERTE IN MAKE.COM CUSTOM VARIABLES EINTRAGEN" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  SHAREPOINT_SITE_ID    = $SiteId" -ForegroundColor White
Write-Host "  SHAREPOINT_DRIVE_ID   = $DriveId" -ForegroundColor White
Write-Host "  SHAREPOINT_SITE_URL   = $SiteUrl" -ForegroundColor White
Write-Host ""
Write-Host "  Library-ID (für Make 'library' Felder): $($Drive.List.Id)" -ForegroundColor White
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

# 8. Verbindung trennen
Disconnect-MgGraph -ErrorAction SilentlyContinue
Write-OK "Verbindung getrennt"

Write-Host "`nNächste Schritte:" -ForegroundColor Cyan
Write-Host "  1. Obige IDs in Make.com Custom Variables eintragen" -ForegroundColor White
Write-Host "  2. Excel-Datei 'Dokumente-Log.xlsx' manuell in SharePoint hochladen" -ForegroundColor White
Write-Host "  3. SharePoint-Ordner im Browser prüfen: $SiteUrl" -ForegroundColor White
Write-Host "  4. WF2 Blueprint importieren (11-wf2-document-processing.blueprint.json)" -ForegroundColor White
