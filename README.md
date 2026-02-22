# gme-app

Desktop client на `PyQt6` для `gme-managment`.

Реализовано:
- экран авторизации и регистрации;
- сохранение сессии (`remember me`) через cookie;
- адаптивный главный экран проектов;
- создание проекта (с загрузкой видео);
- запуск обработки по проекту;
- таблица последних запусков.

## Требования

- Python 3.11+
- запущенный backend `gme-managment`

## Установка

```bash
uv sync
```

## Конфигурация

Переменные окружения:

- `GME_MANAGEMENT_URL` - базовый URL API (по умолчанию `http://localhost:8000/api/v1`)
- `GME_REQUEST_TIMEOUT` - таймаут HTTP в секундах (по умолчанию `15`)
- `GME_SESSION_COOKIE_NAME` - имя cookie сессии (по умолчанию `session_token`)

## Запуск

```bash
uv run python main.py
```
