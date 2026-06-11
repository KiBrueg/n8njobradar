# JobRadar — Backup Reference

**VPS:** `<user>@<your-vps-hostname>` (`<your-vps-ip>`)  
**Доступ:** SSH / Hetzner Console

---

## Что и где лежит

```
/home/kirill/backups/
├── pre-session-YYYY-MM-DD_HH-MM/   ← ручные бэкапы (не ротируются)
│   ├── .env.bak                    — ~/n8n-automation/.env
│   ├── .env.home.bak               — ~/.env
│   ├── docker-compose.yml.bak
│   └── jobradar_db.sql.gz          — pg_dump jobradar
│
└── cfg_YYYY-MM-DD_HH-MM/           ← авто cfg-бэкапы (ротируются, хранится 14 штук)
    ├── .env.bak
    ├── .env.home.bak
    └── docker-compose.yml.bak

/home/kirill/n8n-automation/backups/postgres/
└── hub-YYYYmmdd-HHMMSS.sql.gz      ← авто DB-бэкапы (ротируются, хранится 14 дней)
```

---

## Расписание cron

```
crontab -l  →  (on your VPS)
```

| Время (UTC) | Время (CET) | Скрипт | Что делает |
|-------------|-------------|--------|-----------|
| `03:30` | `05:30` | `deploy/backup.sh` | Postgres dump → `backups/postgres/hub-*.sql.gz` |
| `06:00, 12:00, 20:00` | `08:00, 14:00, 22:00` | `/home/kirill/backup.sh` | `.env` × 2 + `docker-compose.yml` → `backups/cfg_*/` |

---

## Скрипты

### `/home/kirill/backup.sh` — config backup (наш)
- Бэкапит: `~/n8n-automation/.env`, `~/.env`, `docker-compose.yml`
- Хранит последние **14** папок `cfg_*`
- Логирует в syslog: `journalctl -t jobradar-backup`
- Папки `pre-session-*` и другие — **не трогает**

### `~/n8n-automation/deploy/backup.sh` — DB backup (существующий)
- Бэкапит: Postgres dump (`jobradar` DB из контейнера `n8n-automation-postgres-1`)
- Хранит **14 дней** (`RETENTION_DAYS=14`)
- Проверяет что дамп не пустой — если пустой, удаляет и выходит с ошибкой
- Логирует в `~/hub-backup.log`

---

## Ручной бэкап (перед кодингом)

```bash
DEST=~/backups/pre-session-$(date +%Y-%m-%d_%H-%M) && \
  mkdir -p "$DEST" && \
  cp ~/n8n-automation/.env "$DEST/.env.bak" && \
  cp ~/.env "$DEST/.env.home.bak" && \
  cp ~/n8n-automation/docker-compose.yml "$DEST/docker-compose.yml.bak" && \
  docker exec n8n-automation-postgres-1 pg_dump -U hub jobradar \
    | gzip > "$DEST/jobradar_db.sql.gz" && \
  ls -lah "$DEST/"
```

> Результат в папке `pre-session-*` — **никогда не ротируется** автоматически.

---

## Восстановление

### Восстановить DB из авто-дампа (deploy/backup.sh)
```bash
gunzip -c ~/n8n-automation/backups/postgres/hub-YYYYMMDD-HHMMSS.sql.gz \
  | docker exec -i n8n-automation-postgres-1 psql -U hub jobradar
```

### Восстановить DB из ручного pre-session бэкапа
```bash
gunzip -c ~/backups/pre-session-YYYY-MM-DD_HH-MM/jobradar_db.sql.gz \
  | docker exec -i n8n-automation-postgres-1 psql -U hub jobradar
```

### Восстановить .env
```bash
cp ~/backups/cfg_YYYY-MM-DD_HH-MM/.env.bak ~/n8n-automation/.env
# Перезапустить n8n чтобы подхватил новый .env:
cd ~/n8n-automation && docker compose up -d n8n
```

---

## Проверка состояния

```bash
# Посмотреть все бэкапы
ls -lah ~/backups/
ls -lah ~/n8n-automation/backups/postgres/ | tail -5

# Последние записи в логе cfg-бэкапов
journalctl -t jobradar-backup -n 20

# Последние записи в логе DB-бэкапов
tail -20 ~/hub-backup.log
```

---

## Источник

Скрипт в проекте: [`scripts/backup.sh`](../scripts/backup.sh)  
Деплой: см. [`vps-ops` в memory](../memory/vps-ops.md) или [`flows.md`](../n8n/flows.md#backup-script)
