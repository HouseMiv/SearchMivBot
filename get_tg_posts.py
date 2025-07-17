from telethon import TelegramClient
import json
import sys
import os

# Устанавливаем UTF-8 кодировку для корректного вывода
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass  # Если не поддерживается, используем файл

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
bot_token = os.environ['TG_BOT_TOKEN']
channel_username = os.environ.get('TG_CHANNEL', 'HouseMiva')

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

async def main():
    await client.start()
    print('Авторизация прошла успешно!')
    
    posts = []
    async for message in client.iter_messages(channel_username, limit=5):
        if message.text:  # Только текстовые сообщения
            posts.append({
                'id': message.id,
                'text': message.text,
                'date': message.date.isoformat(),
                'link': f'https://t.me/HouseMiva/{message.id}'
            })
    
    # Пробуем вывести в консоль, если не получается - сохраняем в файл
    try:
        json_output = json.dumps(posts, ensure_ascii=False, indent=2)
        print(json_output)
    except UnicodeEncodeError:
        # Если не удалось вывести в консоль, сохраняем в файл
        with open('telegram_posts.json', 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        print('Данные сохранены в telegram_posts.json')

import asyncio
asyncio.run(main())