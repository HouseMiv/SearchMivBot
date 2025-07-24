# SearchMivBot
## Telegram Channel Posts Archiver

Этот проект — простой скрипт на Python для получения последних сообщений из Telegram-канала и сохранения их в JSON файл.

---
## Используемые технологии

- [Telethon](https://docs.telethon.dev/) — асинхронная библиотека для работы с Telegram API  
- [python-dotenv](https://github.com/theskumar/python-dotenv) — для безопасного управления конфиденциальными данными  
- Python 3.7+ с поддержкой `asyncio`
  
---
## Описание
Скрипт выполняет авторизацию в Telegram под вашим аккаунтом, подключается к указанному каналу и выгружает последние 5 текстовых сообщений.  
Результаты сохраняются в файл `telegram_posts.json` с кодировкой UTF-8.
