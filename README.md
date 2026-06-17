# SearchMivBot

**Локальный архиватор Telegram-канала** — собирает посты в `telegram_posts.json` для [HouseMiv](https://github.com/HouseMiv/About-me).
---

## Используемые технологии
- [Python 3.11+](https://www.python.org/downloads/) - Скрипт и JSON-архив 
- [Telethon](https://docs.telethon.dev/) - Telegram API (MTProto) 
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Секреты в `.env` 
- [PySocks](https://github.com/Anorov/PySocks) - SOCKS5-прокси (опционально) 
---

## Формат архива
```json
{
  "last_message_id": 822,
  "posts": [
    {
      "id": 822,
      "text": "",
      "date": "2026-06-12T03:46:15+00:00",
      "link": "https://t.me/HouseMiva/822",
      "media_type": "voice"
    }
  ]
}
```

| `media_type` | Telegram |
|--------------|----------|
| `photo` | Фото |
| `video` | Видео |
| `video_note` | Кружок |
| `animation` | GIF |
| `sticker` | Стикер |
| `voice` | Голосовое |
| `audio` | Аудио |
| `document` | Файл |
| `null` | Только текст |

`posts[0]` — последний пост. `link` ведёт в Telegram.
---

## Переменные окружения

Полный список — в [`.env.example`](.env.example).

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TG_CHANNEL` | `HouseMiva` | Username канала |
| `TG_OUTPUT_FILE` | `telegram_posts.json` | Путь к архиву |
| `TG_MESSAGE_LIMIT` | `100` | Постов при первом запуске |
| `TG_FULL_BACKUP` | `false` | Вся история при первом запуске |
| `TG_RETRY_COUNT` | `5` | Попыток при сетевых ошибках |
---