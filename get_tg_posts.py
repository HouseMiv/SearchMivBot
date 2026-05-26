from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged

import os
import json
import asyncio
import socket

from typing import Any
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
channel_username = os.environ.get('TG_CHANNEL', 'HouseMiva')

proxy = None
if os.environ.get('TG_PROXY_HOST') and os.environ.get('TG_PROXY_PORT'):
    proxy = (
        'socks5',
        os.environ['TG_PROXY_HOST'],
        int(os.environ['TG_PROXY_PORT']),
    )

client_kwargs: dict[str, Any] = {
    'connection': ConnectionTcpAbridged,
    'request_retries': 10,
    'connection_retries': 10,
    'retry_delay': 2,
    'timeout': 20,
}

if proxy is not None:
    client_kwargs['proxy'] = proxy

client = TelegramClient(
    'session_name',
    api_id,
    api_hash,
    **client_kwargs
)


def ensure_proxy_reachable(
    proxy_value: tuple[str, str, int] | None,
    timeout: float = 2.0
) -> None:
    if proxy_value is None:
        return

    _, host, port = proxy_value

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass

    except OSError as err:
        raise RuntimeError(
            f'Прокси {host}:{port} недоступен. '
            f'Подними SOCKS5 или поправь TG_PROXY_HOST/TG_PROXY_PORT. '
            f'Детали: {err}'
        ) from err


async def main():
    ensure_proxy_reachable(proxy)

    try:
        # Подключение
        await client.connect()

        # Авторизация
        if not await client.is_user_authorized():
            print('Требуется авторизация Telegram...')
            await client.start()

        print('Авторизация прошла успешно!')

        # Проверяем/получаем entity канала
        try:
            entity = await client.get_entity(channel_username)

        except Exception as err:
            raise RuntimeError(
                f'Не удалось получить канал "{channel_username}". '
                f'Проверь username канала. Детали: {err}'
            ) from err

        # Читаем существующие посты
        existing_posts = []

        if os.path.exists('telegram_posts.json'):
            try:
                with open(
                    'telegram_posts.json',
                    'r',
                    encoding='utf-8'
                ) as f:
                    existing_posts = json.load(f)

            except Exception:
                existing_posts = []

        # Получаем новые посты
        new_posts = []

        print(f'Ищем посты в канале: {channel_username}')

        async for message in client.iter_messages(entity, limit=10):

            text_preview = (
                message.text[:50]
                if message.text
                else 'Нет текста'
            )

            print(
                f'Найдено сообщение: '
                f'ID={message.id}, '
                f'Текст={text_preview}...'
            )

            if message.text:
                new_posts.append({
                    'id': message.id,
                    'text': message.text,
                    'date': message.date.isoformat(),
                    'link': f'https://t.me/{channel_username}/{message.id}'
                })

        print(
            f'Всего найдено текстовых сообщений: '
            f'{len(new_posts)}'
        )

        # Обновляем файл
        if new_posts:

            posts_changed = False

            # Проверка количества
            if len(existing_posts) != len(new_posts):
                posts_changed = True

            else:
                # Проверка ID
                for i, new_post in enumerate(new_posts):

                    if (
                        i >= len(existing_posts)
                        or existing_posts[i]['id'] != new_post['id']
                    ):
                        posts_changed = True
                        break

            if posts_changed:

                with open(
                    'telegram_posts.json',
                    'w',
                    encoding='utf-8'
                ) as f:
                    json.dump(
                        new_posts,
                        f,
                        ensure_ascii=False,
                        indent=2
                    )

                print(f'Обновлено {len(new_posts)} постов')

            else:
                print('Новых постов нет, файл не изменён')

        else:
            # Если постов нет
            if existing_posts:
                print(
                    'Постов в канале нет, '
                    'оставляем последние сохранённые'
                )

            else:
                with open(
                    'telegram_posts.json',
                    'w',
                    encoding='utf-8'
                ) as f:
                    json.dump([], f, ensure_ascii=False, indent=2)

                print('Постов нет, создан пустой файл')

    except (
        TimeoutError,
        ConnectionError,
        OSError,
        RPCError
    ) as err:

        raise RuntimeError(
            'Нет соединения с Telegram. '
            'Проверь прокси/VPN/фаервол. '
            f'Детали: {err}'
        ) from err

    finally:
        await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())