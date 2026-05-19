import logging

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from formatters import apt_view_keyboard, format_plain_card
from joymi_api import JoymiClient
from list_browser import filter_key
from media import delete_messages, send_apartment_card
from models import Category
from storage import ApartmentStore

log = logging.getLogger(__name__)


async def list_all_entries(
    store: ApartmentStore, filter_id: str | None, category: Category
) -> list[tuple[str, int]]:
    entries, _ = await store.list_entries(filter_id, category, 0, 100_000)
    return entries


def find_index(entries: list[tuple[str, int]], entry_fid: str, apt_id: int) -> int:
    for i, (fid, aid) in enumerate(entries):
        if fid == entry_fid and aid == apt_id:
            return i
    return 0


async def show_apt_at_index(
    target: Message | CallbackQuery | Bot,
    store: ApartmentStore,
    api: JoymiClient,
    *,
    browse_filter_id: str | None,
    browse_category: Category,
    index: int,
    chat_id: int | None = None,
) -> None:
    entries = await list_all_entries(store, browse_filter_id, browse_category)
    if not entries:
        text = "Список пуст"
        if isinstance(target, Message):
            await target.answer(text)
        return

    index = max(0, min(index, len(entries) - 1))
    entry_fid, apt_id = entries[index]

    flt = await store.get_filter(entry_fid)
    if not flt:
        text = "Фильтр не найден"
        if isinstance(target, Message):
            await target.answer(text)
        return

    apt = await store.get_apartment(apt_id)
    plain = apt.get("plain") if apt else None
    if not plain:
        try:
            plain = await api.fetch_plain(apt_id)
            await store.save_apartment(apt_id, plain_data=plain)
        except Exception as e:
            log.warning("plain %s: %s", apt_id, e)
            if isinstance(target, Message):
                await target.answer(f"Ошибка: {e}")
            elif isinstance(target, CallbackQuery):
                await target.answer(str(e), show_alert=True)
            return

    pos = f"{index + 1}/{len(entries)}"
    text = format_plain_card(plain, filter_title=f"{flt['title']} · {pos}")
    markup = apt_view_keyboard(
        browse_filter_id,
        browse_category,
        index,
        len(entries),
        entry_fid,
        apt_id,
    )

    if isinstance(target, CallbackQuery):
        bot = target.bot
        cid = target.message.chat.id if target.message else chat_id
        await target.answer()
    elif isinstance(target, Message):
        bot = target.bot
        cid = target.chat.id
    else:
        bot = target
        cid = chat_id

    old_ids = await store.pop_card_message_ids(cid)
    await delete_messages(bot, cid, old_ids)

    ids = await send_apartment_card(bot, cid, plain, text=text, reply_markup=markup)
    await store.set_card_message_ids(cid, ids)


async def show_apt_by_ids(
    target: Message,
    store: ApartmentStore,
    api: JoymiClient,
    entry_filter_id: str,
    apt_id: int,
) -> None:
    """Открыть /apt_{fid}_{id} — листание в категории этой квартиры в этом фильтре."""
    category = await store.get_category(entry_filter_id, apt_id)
    entries = await list_all_entries(store, entry_filter_id, category)
    index = find_index(entries, entry_filter_id, apt_id)
    await show_apt_at_index(
        target,
        store,
        api,
        browse_filter_id=entry_filter_id,
        browse_category=category,
        index=index,
    )
