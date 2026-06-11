# Test Pin Data — Gmail Flow

6 тест-кейсов для проверки всех веток Gmail flow через n8n Pin Data.

## Как использовать

1. В n8n открыть **JobRadar — Flow 1: Gmail**
2. Кликнуть на **Gmail Trigger**
3. Кнопка **Pin** → вставить содержимое нужного JSON файла
4. Запустить через **Test workflow**

## Тест-кейсы и ожидаемые результаты

| Файл | Сценарий | Ожидаемый результат |
|------|----------|---------------------|
| `01_jobrapido_digest.json` | Job digest от Jobrapido | `platform_notification`, `is_job_related: true`, `action: log_only`, `priority_level: 3` |
| `02_interview_invite.json` | Приглашение на интервью с датой | `interview_invite`, `action: add_interview`, `interview_date: 2026-06-16T12:00:00Z`, `IF: interview_date` → true ветка |
| `03_priority_high_recruit.json` | Рекрутер обращается по имени + контекст LinkedIn | `hr_invite`, `priority_level: 1`, `priority: high`, `IF: priority = high` → true ветка |
| `04_rejection.json` | Отказ после собеседования | `rejection`, `action: update_stage`, `stage: rejected` |
| `05_newsletter_ignore.json` | Курс-буткамп без вакансий | `newsletter`, `is_job_related: false`, `action: ignore` → поток уходит в `Stop: Not Job Related` |
| `06_platform_notification_applied.json` | Подтверждение заявки от StepStone | `platform_notification`, `stage: applied`, `action: log_only`, `priority_level: 3` |

## Что проверяем по каждой ветке flow

- **IF: is_job_related** → false → Stop: Not Job Related (кейс #5)
- **IF: is_job_related** → true → дальше по flow (кейсы #1,2,3,4,6)
- **IF: interview_date present** → true (кейс #2), false (остальные)
- **IF: priority = high** → true (кейс #3), false (остальные)
- **Map Category → Gmail Label** → правильный label по category
- **IF: label_found** → found/not_found ветка
- **Google Calendar: Create Event** → только при interview_date (кейс #2)
- **Telegram: Job Alert** → только при priority=high (кейс #3)
