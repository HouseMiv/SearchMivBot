import asyncio
import json
import logging
import os
import random
import socket
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from telethon.tl.custom.message import Message

logger = logging.getLogger(__name__)

T = TypeVar('T')

NETWORK_ERRORS = (
    TimeoutError,
    ConnectionError,
    OSError,
    RPCError,
)

DEFAULT_RETRIES = 5
DEFAULT_MAX_DELAY = 60


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    api_id: int
    api_hash: str
    channel_username: str
    output_file: str
    message_limit: int
    full_backup: bool
    proxy: tuple[str, str, int] | None
    retry_count: int = DEFAULT_RETRIES
    retry_max_delay: int = DEFAULT_MAX_DELAY


def backoff_delay(attempt: int, max_delay: int = DEFAULT_MAX_DELAY) -> float:
    return min((2 ** (attempt + 1)) + random.random(), max_delay)


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    *,
    retries: int = DEFAULT_RETRIES,
    max_delay: int = DEFAULT_MAX_DELAY,
    retryable_errors: tuple[type[BaseException], ...] = NETWORK_ERRORS,
) -> T:
    last_error: BaseException | None = None

    for attempt in range(retries):
        try:
            return await func()
        except retryable_errors as err:
            last_error = err

            if attempt == retries - 1:
                break

            delay = backoff_delay(attempt, max_delay)
            logger.warning(
                'Сетевая ошибка, повтор %d/%d через %.1f с: %s',
                attempt + 1,
                retries,
                delay,
                err,
            )
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


def get_last_message_id(posts: list[dict[str, Any]]) -> int:
    return max((post['id'] for post in posts), default=0)


def load_archive(path: str) -> dict[str, Any]:
    empty_archive = {'last_message_id': 0, 'posts': []}

    if not os.path.exists(path):
        return empty_archive

    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as err:
        logger.warning('Не удалось прочитать %s: %s', path, err)
        return empty_archive

    if not isinstance(data, dict):
        logger.warning('Неверный формат архива в %s', path)
        return empty_archive

    posts = data.get('posts', [])
    last_message_id = data.get('last_message_id', 0)

    if not last_message_id and posts:
        last_message_id = get_last_message_id(posts)

    return {
        'last_message_id': last_message_id,
        'posts': posts,
    }


def merge_posts(
    existing_posts: list[dict[str, Any]],
    new_posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    posts_by_id = {post['id']: post for post in existing_posts}

    for post in new_posts:
        posts_by_id[post['id']] = post

    return sorted(
        posts_by_id.values(),
        key=lambda post: post['id'],
        reverse=True,
    )


def prune_deleted_posts(
    posts: list[dict[str, Any]],
    existing_ids: set[int],
) -> tuple[list[dict[str, Any]], list[int]]:
    kept_posts: list[dict[str, Any]] = []
    removed_ids: list[int] = []

    for post in posts:
        if post['id'] in existing_ids:
            kept_posts.append(post)
        else:
            removed_ids.append(post['id'])

    return kept_posts, removed_ids


GET_MESSAGES_BATCH_SIZE = 100


async def fetch_existing_post_ids(
    client: TelegramClient,
    entity: Any,
    post_ids: list[int],
) -> set[int]:
    if not post_ids:
        return set()

    existing_ids: set[int] = set()

    for index in range(0, len(post_ids), GET_MESSAGES_BATCH_SIZE):
        batch = post_ids[index : index + GET_MESSAGES_BATCH_SIZE]
        result = await client.get_messages(entity, ids=batch)

        if result is None:
            continue

        batch_messages = result if isinstance(result, list) else [result]

        for message in batch_messages:
            if message is not None:
                existing_ids.add(message.id)

    return existing_ids


def save_archive(path: str, archive: dict[str, Any]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def validate_config(env: Mapping[str, str] | None = None) -> None:
    source = env if env is not None else os.environ

    api_id = source.get('TG_API_ID', '').strip()
    if not api_id:
        raise ConfigError('TG_API_ID is not configured')

    try:
        int(api_id)
    except ValueError as err:
        raise ConfigError('TG_API_ID must be an integer') from err

    api_hash = source.get('TG_API_HASH', '').strip()
    if not api_hash:
        raise ConfigError('TG_API_HASH is not configured')

    channel = source.get('TG_CHANNEL', 'HouseMiva').strip()
    if not channel:
        raise ConfigError('TG_CHANNEL is empty')

    message_limit = source.get('TG_MESSAGE_LIMIT', '100').strip()
    full_backup = source.get('TG_FULL_BACKUP', '').lower() in ('1', 'true', 'yes')

    if not full_backup:
        try:
            limit = int(message_limit)
        except ValueError as err:
            raise ConfigError('TG_MESSAGE_LIMIT must be an integer') from err

        if limit < 1:
            raise ConfigError('TG_MESSAGE_LIMIT must be at least 1')

    proxy_enabled = source.get('TG_PROXY_ENABLED', '').lower() not in ('0', 'false', 'no')
    proxy_host = source.get('TG_PROXY_HOST', '').strip()
    proxy_port = source.get('TG_PROXY_PORT', '').strip()

    if proxy_enabled and (proxy_host or proxy_port):
        if not proxy_host:
            raise ConfigError('TG_PROXY_HOST is not configured')
        if not proxy_port:
            raise ConfigError('TG_PROXY_PORT is not configured')

        try:
            port = int(proxy_port)
        except ValueError as err:
            raise ConfigError('TG_PROXY_PORT must be an integer') from err

        if port < 1 or port > 65535:
            raise ConfigError('TG_PROXY_PORT must be between 1 and 65535')


def load_config(env: Mapping[str, str] | None = None) -> Config:
    source = env if env is not None else os.environ

    validate_config(source)

    proxy = None
    proxy_host = source.get('TG_PROXY_HOST', '').strip()
    proxy_port = source.get('TG_PROXY_PORT', '').strip()
    proxy_enabled = source.get('TG_PROXY_ENABLED', '').lower() not in ('0', 'false', 'no')

    if proxy_enabled and proxy_host and proxy_port:
        proxy = ('socks5', proxy_host, int(proxy_port))

    return Config(
        api_id=int(source['TG_API_ID']),
        api_hash=source['TG_API_HASH'].strip(),
        channel_username=source.get('TG_CHANNEL', 'HouseMiva').strip(),
        output_file=source.get('TG_OUTPUT_FILE', 'telegram_posts.json').strip(),
        message_limit=int(source.get('TG_MESSAGE_LIMIT', '100')),
        full_backup=source.get('TG_FULL_BACKUP', '').lower() in ('1', 'true', 'yes'),
        proxy=proxy,
        retry_count=int(source.get('TG_RETRY_COUNT', str(DEFAULT_RETRIES))),
        retry_max_delay=int(source.get('TG_RETRY_MAX_DELAY', str(DEFAULT_MAX_DELAY))),
    )


def create_client(config: Config) -> TelegramClient:
    client_kwargs: dict[str, Any] = {
        'connection': ConnectionTcpAbridged,
        'request_retries': 3,
        'connection_retries': 3,
        'retry_delay': 2,
        'timeout': 20,
    }

    if config.proxy is not None:
        client_kwargs['proxy'] = config.proxy

    return TelegramClient(
        'session_name',
        config.api_id,
        config.api_hash,
        **client_kwargs,
    )


def _check_proxy_connection(host: str, port: int, timeout: float) -> None:
    with socket.create_connection((host, port), timeout=timeout):
        pass


async def ensure_proxy_reachable(
    proxy_value: tuple[str, str, int] | None,
    timeout: float = 2.0,
    retries: int = DEFAULT_RETRIES,
    max_delay: int = DEFAULT_MAX_DELAY,
) -> None:
    if proxy_value is None:
        return

    _, host, port = proxy_value

    async def check() -> None:
        await asyncio.to_thread(_check_proxy_connection, host, port, timeout)

    try:
        await retry_with_backoff(
            check,
            retries=retries,
            max_delay=max_delay,
        )
    except OSError as err:
        raise RuntimeError(
            f'Прокси {host}:{port} недоступен. '
            f'Подними SOCKS5 или поправь TG_PROXY_HOST/TG_PROXY_PORT. '
            f'Детали: {err}'
        ) from err


def _detect_media_type(message: Message) -> str | None:
    if message.photo:
        return 'photo'
    if message.sticker:
        return 'sticker'
    if message.voice:
        return 'voice'
    if message.video_note:
        return 'video_note'
    if message.video:
        return 'video'
    if message.gif:
        return 'animation'
    if message.audio:
        return 'audio'
    if message.document:
        return 'document'
    return None


def message_to_post(message: Message, channel: str) -> dict[str, Any]:
    date = message.date.isoformat() if message.date is not None else ''

    return {
        'id': message.id,
        'text': message.text or '',
        'date': date,
        'link': f'https://t.me/{channel}/{message.id}',
        'media_type': _detect_media_type(message),
    }


async def fetch_posts(
    client: TelegramClient,
    entity: Any,
    config: Config,
    last_message_id: int,
) -> list[dict[str, Any]]:
    fetched_posts = []

    if last_message_id == 0:
        if config.full_backup:
            logger.info('Первый запуск: полный бэкап канала')
            iterator = client.iter_messages(entity)
        else:
            logger.info(
                'Первый запуск: загрузка последних %d сообщений',
                config.message_limit,
            )
            iterator = client.iter_messages(entity, limit=config.message_limit)
    else:
        logger.info(
            'Инкрементальная загрузка: сообщения с id > %d',
            last_message_id,
        )
        iterator = client.iter_messages(entity, min_id=last_message_id)

    async for message in iterator:
        media_type = _detect_media_type(message)
        text_preview = message.text[:50] if message.text else 'Нет текста'
        media_preview = media_type or 'нет'

        logger.info(
            'Найдено сообщение: ID=%d, media=%s, Текст=%s...',
            message.id,
            media_preview,
            text_preview,
        )

        fetched_posts.append(message_to_post(message, config.channel_username))

    return fetched_posts


async def main():
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    config = load_config()
    client = create_client(config)

    await ensure_proxy_reachable(
        config.proxy,
        retries=config.retry_count,
        max_delay=config.retry_max_delay,
    )

    try:
        await retry_with_backoff(
            client.connect,
            retries=config.retry_count,
            max_delay=config.retry_max_delay,
        )

        if not await client.is_user_authorized():
            logger.info('Требуется авторизация Telegram...')

            async def authorize() -> None:
                await client.start()  # pyright: ignore[reportGeneralTypeIssues]

            await retry_with_backoff(
                authorize,
                retries=config.retry_count,
                max_delay=config.retry_max_delay,
            )

        logger.info('Авторизация прошла успешно')

        try:
            entity = await retry_with_backoff(
                lambda: client.get_entity(config.channel_username),
                retries=config.retry_count,
                max_delay=config.retry_max_delay,
            )
        except Exception as err:
            raise RuntimeError(
                f'Не удалось получить канал "{config.channel_username}". '
                f'Проверь username канала. Детали: {err}'
            ) from err

        archive = load_archive(config.output_file)
        existing_posts = archive['posts']
        last_message_id = archive['last_message_id']

        logger.info(
            'Канал: %s, в архиве: %d постов',
            config.channel_username,
            len(existing_posts),
        )

        fetched_posts = await retry_with_backoff(
            lambda: fetch_posts(
                client,
                entity,
                config,
                last_message_id,
            ),
            retries=config.retry_count,
            max_delay=config.retry_max_delay,
        )

        logger.info('Получено новых сообщений: %d', len(fetched_posts))

        merged_posts = merge_posts(existing_posts, fetched_posts)

        if merged_posts:
            existing_ids = await retry_with_backoff(
                lambda: fetch_existing_post_ids(
                    client,
                    entity,
                    [post['id'] for post in merged_posts],
                ),
                retries=config.retry_count,
                max_delay=config.retry_max_delay,
            )
            pruned_posts, removed_ids = prune_deleted_posts(merged_posts, existing_ids)

            if removed_ids:
                logger.info(
                    'Удалены из архива (нет в канале): %s',
                    ', '.join(str(post_id) for post_id in removed_ids),
                )
        else:
            pruned_posts = []
            removed_ids = []

        archive_changed = pruned_posts != existing_posts

        if archive_changed:
            archive = {
                'last_message_id': get_last_message_id(pruned_posts),
                'posts': pruned_posts,
            }
            save_archive(config.output_file, archive)

            added_count = len(pruned_posts) - len(existing_posts) + len(removed_ids)
            logger.info(
                'Архив обновлён: +%d / -%d, всего %d',
                max(added_count, 0),
                len(removed_ids),
                len(pruned_posts),
            )
        elif existing_posts:
            logger.info('Изменений нет, архив без обновлений')
        else:
            save_archive(config.output_file, {'last_message_id': 0, 'posts': []})
            logger.info('Постов нет, создан пустой архив')

    except NETWORK_ERRORS as err:
        raise RuntimeError(
            'Нет соединения с Telegram. '
            'Проверь прокси/VPN/фаервол. '
            f'Детали: {err}'
        ) from err

    finally:
        await client.disconnect()  # pyright: ignore[reportGeneralTypeIssues]


if __name__ == '__main__':
    asyncio.run(main())
