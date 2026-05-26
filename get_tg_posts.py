from telethon import TelegramClient, events
from dotenv import load_dotenv

import os
import json
import asyncio

load_dotenv()

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
channel_username = os.environ.get('TG_CHANNEL', 'HouseMiva')

client = TelegramClient(
    'session_name',
    api_id,
    api_hash
)


async def save_post(message):

    post_data = {
        'id': message.id,
        'text': message.text,
        'date': message.date.isoformat(),
        'link': f'https://t.me/{channel_username}/{message.id}'
    }

    posts = []

    if os.path.exists('telegram_posts.json'):
        try:
            with open(
                'telegram_posts.json',
                'r',
                encoding='utf-8'
            ) as f:
                posts = json.load(f)

        except Exception:
            posts = []

    # Проверяем дубликаты
    exists = any(post['id'] == message.id for post in posts)

    if not exists:
        posts.insert(0, post_data)

        # Храним последние 10
        posts = posts[:10]

        with open(
            'telegram_posts.json',
            'w',
            encoding='utf-8'
        ) as f:
            json.dump(
                posts,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(f'Новый пост сохранён: {message.id}')


@client.on(events.NewMessage(chats=channel_username))
async def handler(event):

    message = event.message

    if message.text:
        print(f'Новый пост: {message.text[:50]}...')
        await save_post(message)


async def main():

    await client.start()

    print('Бот запущен и слушает новые посты...')

    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())