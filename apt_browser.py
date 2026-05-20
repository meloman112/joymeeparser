import logging
from typing import Literal

from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from formatters import apt_view_keyboard, format_plain_card
from joymi_api import JoymiClient
from list_browser import filter_key
from media import delete_messages, send_apartment_card
from models import Category
from storage import ApartmentStore

log = logging.getLogger(__name__)
NavDir = Literal["next", "prev", "stay"]


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


def resolve_nav(
    entries: list[tuple[str, int]],
    entry_fid: str,
    apt_id: int,
    direction: NavDir,
    hint_index: int,
) -> tuple[str, int, int] | None:
    """Следующий/предыдущий с учётом сдвига списка после удаления из категории."""
    if not entries:
        return None

    for i, (fid, aid) in enumerate(entries):
        if fid == entry_fid and aid == apt_id:
            if direction == "next":
                j = min(i + 1, len(entries) - 1)
            elif direction == "prev":
                j = max(i - 1, 0)
            else:
                j = i
            return entries[j][0], entries[j][1], j

    # Объявление ушло из списка (например, помечено 🗑) — берём ту же позицию в новом списке
    idx = max(0, min(hint_index, len(entries) - 1))
    if direction == "next" and hint_index >= len(entries):
        idx = len(entries) - 1
    elif direction == "prev" and hint_index > 0:
        idx = max(0, hint_index - 1)

    fid, aid = entries[idx]
    return fid, aid, idx


async def show_apt_entry(
    target: Message | CallbackQuery | Bot,
    store: ApartmentStore,
    api: JoymiClient,
    *,
    browse_filter_id: str | None,
    browse_category: Category,
    entry_fid: str,
    apt_id: int,
    hint_index: int | None = None,
) -> None:
    entries = await list_all_entries(store, browse_filter_id, browse_category)
    if not entries:
        if isinstance(target, Message):
            await target.answer("Список пуст")
        elif isinstance(target, CallbackQuery):
            await target.answer("Список пуст", show_alert=True)
        return

    idx = hint_index if hint_index is not None else find_index(entries, entry_fid, apt_id)
    idx = max(0, min(idx, len(entries) - 1))

    if (entry_fid, apt_id) not in entries:
        entry_fid, apt_id = entries[idx]

    await _render_apt(
        target,
        store,
        api,
        browse_filter_id=browse_filter_id,
        browse_category=browse_category,
        entry_fid=entry_fid,
        apt_id=apt_id,
        index=idx,
        total=len(entries),
    )


async def navigate_apt(
    target: Message | CallbackQuery,
    store: ApartmentStore,
    api: JoymiClient,
    *,
    browse_filter_id: str | None,
    browse_category: Category,
    entry_fid: str,
    apt_id: int,
    direction: NavDir,
    hint_index: int,
) -> None:
    entries = await list_all_entries(store, browse_filter_id, browse_category)
    resolved = resolve_nav(entries, entry_fid, apt_id, direction, hint_index)
    if not resolved:
        if isinstance(target, CallbackQuery):
            await target.answer("Список пуст", show_alert=True)
        return

    new_fid, new_aid, new_idx = resolved
    await _render_apt(
        target,
        store,
        api,
        browse_filter_id=browse_filter_id,
        browse_category=browse_category,
        entry_fid=new_fid,
        apt_id=new_aid,
        index=new_idx,
        total=len(entries),
    )


async def _render_apt(
    target: Message | CallbackQuery | Bot,
    store: ApartmentStore,
    api: JoymiClient,
    *,
    browse_filter_id: str | None,
    browse_category: Category,
    entry_fid: str,
    apt_id: int,
    index: int,
    total: int,
) -> None:
    flt = await store.get_filter(entry_fid)
    if not flt:
        if isinstance(target, Message):
            await target.answer("Фильтр не найден")
        elif isinstance(target, CallbackQuery):
            await target.answer("Фильтр не найден", show_alert=True)
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

    viewed = await store.is_viewed(entry_fid, apt_id)
    apt_cat = await store.get_category(entry_fid, apt_id)
    pos = f"{index + 1}/{total}"
    text = format_plain_card(
        plain,
        filter_title=f"{flt['title']} · {pos}",
        viewed=viewed,
        apt_category=apt_cat,
        browse_category=browse_category,
    )
    markup = apt_view_keyboard(
        browse_filter_id,
        browse_category,
        index,
        total,
        entry_fid,
        apt_id,
        viewed=viewed,
    )

    if isinstance(target, CallbackQuery):
        bot = target.bot
        cid = target.message.chat.id
        await target.answer()
    elif isinstance(target, Message):
        bot = target.bot
        cid = target.chat.id
    else:
        bot = target
        cid = target  # type: ignore[assignment]

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
    category = await store.get_category(entry_filter_id, apt_id)
    entries = await list_all_entries(store, entry_filter_id, category)
    index = find_index(entries, entry_filter_id, apt_id)
    await show_apt_entry(
        target,
        store,
        api,
        browse_filter_id=entry_filter_id,
        browse_category=category,
        entry_fid=entry_filter_id,
        apt_id=apt_id,
        hint_index=index,
    )
