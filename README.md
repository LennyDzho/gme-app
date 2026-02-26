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

- `GME_MANAGEMENT_URL` - базовый URL API (по умолчанию `http://localhost:8001/api/v1`)
- `GME_VIDEO_SERVICE_URL` - базовый URL video-сервиса (по умолчанию `http://localhost:8000`)
- `GME_AUDIO_SERVICE_URL` - базовый URL audio-сервиса (по умолчанию `http://localhost:8002`)
- `GME_AUDIO_SERVICE_API_KEY` - API key для прямого запроса списка audio-провайдеров из `gme-audio-service` (опционально)
- `GME_REQUEST_TIMEOUT` - таймаут HTTP в секундах (по умолчанию `15`)
- `GME_SESSION_COOKIE_NAME` - имя cookie сессии (по умолчанию `session_token`)

## Запуск

```bash
uv run python main.py
```
