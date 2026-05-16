WORK_MODE            = 1   # 1 — ежедневная проверка / 2 — синхронизация при старте
DAILY_CHECK_HOUR     = 23  # час чтения новых сообщений канала (режим 1)
PENDING_CHECK_HOUR   = 6   # час применения отложенных изменений (режим 1, молча)
PENDING_NOTIFY_HOUR  = 8   # час отправки уведомлений о применённых изменениях
PENDING_NOTIFY_MINUTE = 10 # минута отправки уведомлений (08:10)
SYNC_LOOKBACK_DAYS   = 30  # дней назад для режима 2 при первом запуске без истории

CHANNEL      = 'wb_api_notifications'
SESSION_NAME = 'wb_monitor_session'
