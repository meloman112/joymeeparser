import logging
from typing import Any

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto, Message

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _client_get() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    return _client


async def close_media_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def image_urls_from_plain(plain: dict[str, Any]) -> list[str]:
    images = plain.get("images") or []
    sorted_imgs = sorted(images, key=lambda x: (not x.get("is_main"), x.get("order", 999)))
    urls: list[str] = []
    seen: set[str] = set()
    for img in sorted_imgs:
        url = img.get("url")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


async def download_photo(url: str) -> bytes | None:
    try:
        resp = await _client_get().get(url)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        log.warning("photo download %s: %s", url[:80], e)
        return None


async def send_apartment_photos(
    bot: Bot,
    chat_id: int,
    plain: dict[str, Any],
    *,
    reply_to_message_id: int | None = None,
) -> list[int]:
    """Скачивает и шлёт все фото (альбомами по 10). Возвращает message_id."""
    urls = image_urls_from_plain(plain)
    if not urls:
        return []

    message_ids: list[int] = []
    sent = 0
    for i in range(0, len(urls), 10):
        chunk = urls[i : i + 10]
        media: list[InputMediaPhoto] = []
        for j, url in enumerate(chunk):
            data = await download_photo(url)
            if not data:
                continue
            media.append(
                InputMediaPhoto(
                    media=BufferedInputFile(
                        data, filename=f"{plain.get('id', 'x')}_{i + j}.webp"
                    )
                )
            )

        if not media:
            continue

        messages = await bot.send_media_group(
            chat_id,
            media,
            reply_to_message_id=reply_to_message_id if sent == 0 else None,
        )
        message_ids.extend(m.message_id for m in messages)
        sent += len(media)

    return message_ids


async def send_apartment_card(
    target: Message | Bot,
    chat_id: int,
    plain: dict[str, Any],
    *,
    text: str,
    reply_markup=None,
    reply_to_message_id: int | None = None,
) -> list[int]:
    """Текст + фото. Возвращает все message_id для последующего удаления."""
    bot = target.bot if isinstance(target, Message) else target
    message_ids: list[int] = []

    msg = await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        reply_to_message_id=reply_to_message_id,
    )
    message_ids.append(msg.message_id)

    photo_ids = await send_apartment_photos(
        bot,
        chat_id,
        plain,
        reply_to_message_id=msg.message_id,
    )
    message_ids.extend(photo_ids)

    if not photo_ids and plain.get("images"):
        warn = await bot.send_message(
            chat_id,
            "⚠️ Фото не скачались",
            reply_to_message_id=msg.message_id,
        )
        message_ids.append(warn.message_id)

    return message_ids


async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception as e:
            log.debug("delete msg %s: %s", mid, e)
