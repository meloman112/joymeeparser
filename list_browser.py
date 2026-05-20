import math
from typing import Any

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from formatters import format_short_list_item
from models import Category
from storage import ApartmentStore

PAGE_SIZE = 5
CATEGORIES = {c.value for c in Category}


def parse_list_args(parts: list[str], filter_ids: set[str]) -> tuple[str | None, Category]:
    """filter_id None = все фильтры."""
    if not parts:
        return None, Category.UNVERIFIED
    if parts[0] in CATEGORIES:
        return None, Category(parts[0])
    if parts[0] in filter_ids:
        cat = Category(parts[1]) if len(parts) > 1 else Category.UNVERIFIED
        return parts[0], cat
    return None, Category(parts[0])


def filter_key(filter_id: str | None) -> str:
    return filter_id or "all"


def pagination_keyboard(
    filter_id: str | None,
    category: Category,
    page: int,
    total_pages: int,
    *,
    page_entries: list[tuple[str, int]] | None = None,
    base_index: int = 0,
) -> InlineKeyboardMarkup:
    fk = filter_key(filter_id)
    cat = category.value
    rows: list[list[InlineKeyboardButton]] = []

    if page_entries:
        rows.append(
            [
                InlineKeyboardButton(
                    text=str(base_index + i + 1),
                    callback_data=f"open:{fk}:{cat}:{base_index + i}",
                )
                for i in range(len(page_entries))
            ]
        )

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"lst:{fk}:{cat}:{page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1} / {total_pages}",
                callback_data="noop:page",
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="Вперёд ▶️",
                    callback_data=f"lst:{fk}:{cat}:{page + 1}",
                )
            )
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_list_page(
    store: ApartmentStore,
    filter_id: str | None,
    category: Category,
    page: int,
) -> tuple[str, InlineKeyboardMarkup | None, int]:
    entries, total = await store.list_entries(filter_id, category, page * PAGE_SIZE, PAGE_SIZE)
    total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
    page = min(page, total_pages - 1)

    if page > 0 and not entries:
        entries, total = await store.list_entries(
            filter_id, category, page * PAGE_SIZE, PAGE_SIZE
        )

    fk = filter_key(filter_id)
    scope = f"#{fk}" if filter_id else "все фильтры"
    header = f"<b>{scope}</b> · {category.label_ru}"

    if total == 0:
        return f"{header}\n\nПусто", None, 0

    lines = [f"{header} · {total} шт · стр. {page + 1}/{total_pages}\n"]
    base_index = page * PAGE_SIZE
    for i, (fid, apt_id) in enumerate(entries):
        apt = await store.get_apartment(apt_id)
        if apt:
            viewed = await store.is_viewed(fid, apt_id)
            lines.append(
                format_short_list_item(
                    apt, fid, category, base_index + i, total, viewed=viewed
                )
            )

    markup = pagination_keyboard(
        filter_id,
        category,
        page,
        total_pages,
        page_entries=entries,
        base_index=base_index,
    )
    return "\n".join(lines), markup, total


async def send_list_page(
    target: Message | CallbackQuery,
    store: ApartmentStore,
    filter_id: str | None,
    category: Category,
    page: int = 0,
    *,
    edit: bool = False,
) -> None:
    text, markup, total = await build_list_page(store, filter_id, category, page)
    if total == 0 and not markup:
        if edit and isinstance(target, CallbackQuery) and target.message:
            await target.message.edit_text(text, parse_mode="HTML")
        elif isinstance(target, Message):
            await target.answer(text, parse_mode="HTML")
        elif isinstance(target, CallbackQuery):
            await target.message.answer(text, parse_mode="HTML")
        return

    if edit and isinstance(target, CallbackQuery) and target.message:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await target.answer()
    elif isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
    elif isinstance(target, CallbackQuery) and target.message:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await target.answer()
