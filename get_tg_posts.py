from telethon import TelegramClient
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
channel_username = os.environ.get('TG_CHANNEL', 'HouseMiva')

client = TelegramClient('session_name', api_id, api_hash)

async def main():
    await client.start()
    print('Авторизация прошла успешно!')

    # Читаем существующие посты, если файл есть
    existing_posts = []
    if os.path.exists('telegram_posts.json'):
        try:
            with open('telegram_posts.json', 'r', encoding='utf-8') as f:
                existing_posts = json.load(f)
        except:
            existing_posts = []

    # Получаем новые посты
    new_posts = []
    async for message in client.iter_messages(channel_username, limit=5):
        if message.text:
            new_posts.append({
                'id': message.id,
                'text': message.text,
                'date': message.date.isoformat(),
                'link': f'https://t.me/{channel_username}/{message.id}'
            })

    # Если есть новые посты, обновляем файл
    if new_posts:
        # Проверяем, есть ли изменения в постах
        posts_changed = False
        
        # Если количество постов изменилось или посты разные
        if len(existing_posts) != len(new_posts):
            posts_changed = True
        else:
            # Сравниваем ID постов
            for i, new_post in enumerate(new_posts):
                if i >= len(existing_posts) or existing_posts[i]['id'] != new_post['id']:
                    posts_changed = True
                    break
        
        if posts_changed:
            # Сохраняем все новые посты (до 5 штук)
            with open('telegram_posts.json', 'w', encoding='utf-8') as f:
                json.dump(new_posts, f, ensure_ascii=False, indent=2)
            print(f'Обновлено {len(new_posts)} постов')
        else:
            # Посты не изменились, ничего не меняем
            print('Новых постов нет, файл не изменён')
    else:
        # Если постов нет вообще, но есть сохранённые - оставляем их
        if existing_posts:
            print('Постов в канале нет, оставляем последние сохранённые')
        else:
            # Если ничего нет - создаём пустой массив
            with open('telegram_posts.json', 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print('Постов нет, создан пустой файл')

import asyncio
asyncio.run(main())