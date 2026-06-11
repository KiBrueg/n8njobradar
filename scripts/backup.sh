#!/usr/bin/env bash
# ==============================================================================
# JobRadar — PostgreSQL Backup Script
# Location on VPS: /home/kirill/backup.sh
# ==============================================================================
# Two backup tiers:
#   auto    — jobradar_YYYY-MM-DD_HH-MM/  — rotated, keep KEEP_AUTO (default 14)
#   manual  — pre-session-*/              — never auto-deleted
#
# Usage:
#   ./backup.sh               — run auto backup
#   ./backup.sh --quiet       — suppress stdout (for cron)
#
# Cron (3x/day at 06:00, 12:00, 20:00 UTC = 08:00, 14:00, 22:00 CET):
#   0 6,12,20 * * * /home/kirill/backup.sh --quiet
# ==============================================================================

set -euo pipefail

BACKUP_DIR="/home/kirill/backups"
CONTAINER="n8n-automation-postgres-1"
DB_USER="hub"
DB_NAME="jobradar"
COMPOSE_DIR="/home/kirill/n8n-automation"
KEEP_AUTO=14          # how many auto backups to keep
MIN_DUMP_KB=5         # if dump is smaller than this — treat as broken, abort rotation
QUIET="${1:-}"

log() {
  local msg="$*"
  if [[ "$QUIET" != "--quiet" ]]; then
    echo "[backup] $msg"
  fi
  logger -t jobradar-backup "$msg"
}

die() {
  log "ERROR: $*"
  logger -t jobradar-backup "ERROR: $*"
  exit 1
}

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

command -v docker &>/dev/null || die "docker not found in PATH"

docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$" \
  || die "container '${CONTAINER}' is not running"

# ---------------------------------------------------------------------------
# Create timestamped backup directory
# ---------------------------------------------------------------------------

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
DEST="${BACKUP_DIR}/jobradar_${TIMESTAMP}"
mkdir -p "$DEST"

log "Starting backup → ${DEST}"

# ---------------------------------------------------------------------------
# 1. .env files (most critical — API keys, passwords)
# ---------------------------------------------------------------------------

if [[ -f "${COMPOSE_DIR}/.env" ]]; then
  cp "${COMPOSE_DIR}/.env" "${DEST}/.env.bak"
  log "OK — .env ($(du -sh "${DEST}/.env.bak" | cut -f1))"
else
  log "WARN — ${COMPOSE_DIR}/.env not found, skipping"
fi

if [[ -f "/home/kirill/.env" ]]; then
  cp "/home/kirill/.env" "${DEST}/.env.home.bak"
  log "OK — ~/.env ($(du -sh "${DEST}/.env.home.bak" | cut -f1))"
fi

# ---------------------------------------------------------------------------
# 2. docker-compose.yml
# ---------------------------------------------------------------------------

if [[ -f "${COMPOSE_DIR}/docker-compose.yml" ]]; then
  cp "${COMPOSE_DIR}/docker-compose.yml" "${DEST}/docker-compose.yml.bak"
  log "OK — docker-compose.yml"
fi

# ---------------------------------------------------------------------------
# 3. Postgres dump
# ---------------------------------------------------------------------------

DUMPFILE="${DEST}/jobradar_db.sql.gz"

if docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$DUMPFILE"; then
  DUMP_KB=$(du -k "$DUMPFILE" | cut -f1)
  if (( DUMP_KB < MIN_DUMP_KB )); then
    # Dump is suspiciously small — keep the backup dir but abort rotation
    log "WARN — dump is only ${DUMP_KB}KB (expected >=${MIN_DUMP_KB}KB) — skipping rotation to protect old backups"
    log "Manual check needed: ${DUMPFILE}"
    exit 0
  fi
  log "OK — pg_dump ($(du -sh "$DUMPFILE" | cut -f1))"
else
  log "ERROR: pg_dump failed — removing partial dump"
  rm -f "$DUMPFILE"
  die "pg_dump failed"
fi

# ---------------------------------------------------------------------------
# 4. Rotate old AUTO backups (never touch pre-session-* or other manual dirs)
# ---------------------------------------------------------------------------

# Only count dirs matching jobradar_* pattern (auto backups)
AUTO_BACKUPS=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "jobradar_*" | sort)
AUTO_COUNT=$(echo "$AUTO_BACKUPS" | grep -c . || true)

if (( AUTO_COUNT > KEEP_AUTO )); then
  TO_DELETE=$(( AUTO_COUNT - KEEP_AUTO ))
  log "Rotating — removing ${TO_DELETE} old auto backup(s) (keeping ${KEEP_AUTO})"
  echo "$AUTO_BACKUPS" | head -n "$TO_DELETE" | while read -r dir; do
    rm -rf "$dir"
    log "Deleted: $dir"
  done
fi

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------

log "Done. Auto backups kept: $(find "$BACKUP_DIR" -maxdepth 1 -type d -name "jobradar_*" | wc -l)/${KEEP_AUTO}"
log "Latest: ${DEST}"
