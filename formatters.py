from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import Category


def filter_key(filter_id: str | None) -> str:
    return filter_id or "all"


def format_plain_card(
    data: dict[str, Any],
    *,
    is_new: bool = False,
    filter_title: str | None = None,
) -> str:
    title = data.get("title") or "—"
    price = data.get("price")
    district = (data.get("district") or {}).get("name", "")
    address = data.get("address_line") or ""
    rooms = data.get("room_qty")
    floor = data.get("floor_number")
    floors = data.get("floors_count")
    area = data.get("area_m2")
    desc = (data.get("description") or "")[:800]
    phone = data.get("phone_number") or (data.get("seller") or {}).get("phone", "")
    apt_id = data.get("id")
    lat = data.get("latitude")
    lng = data.get("longitude")
    n_photos = len(data.get("images") or [])

    seller = data.get("seller") or {}
    seller_name = seller.get("fullname") or seller.get("profile_name") or ""

    header = "🆕 НОВАЯ\n" if is_new else ""
    if filter_title:
        header += f"🔎 {filter_title}\n"
    lines = [
        f"{price} y.e - {rooms} комн \n<b>{title}</b>",
        f"💰 {price} y.e. · id <code>{apt_id}</code>",
        f"📍 {district}" + (f", {address}" if address else ""),
        f"🏠 {rooms} комн · {area} m² · этаж {floor}/{floors}",
    ]
    if seller_name:
        lines.append(f"👤 {seller_name}")
    if phone:
        lines.append(f"📞 <code>{phone}</code>")
    if lat and lng:
        lines.append(
            f"🗺 <a href='https://yandex.ru/maps/?pt={lng},{lat}&z=17&l=map'>Яндекс.Карты</a>"
        )
    if n_photos:
        lines.append(f"📷 {n_photos} фото ниже")
    if desc:
        lines.append(f"\n{desc}")

    return "\n".join(lines)


def format_short_list_item(
    apt: dict[str, Any],
    filter_id: str,
    category: Category,
    index: int,
    total: int,
) -> str:
    m = apt.get("map") or {}
    p = apt.get("plain") or {}
    apt_id = m.get("id") or p.get("id")
    price = m.get("price") or p.get("price")
    title = p.get("title", f"id {apt_id}")
    return (
        f"{index + 1}. {category.label_ru} · <b>{price}</b> y.e. · {title[:40]}\n"
        f"   /apt_{filter_id}_{apt_id}"
    )


def _cat_cb(
    browse_fk: str,
    browse_cat: str,
    index: int,
    entry_fid: str,
    apt_id: int,
    cat: str,
) -> str:
    return f"cat:{browse_fk}:{browse_cat}:{index}:{entry_fid}:{apt_id}:{cat}"


def apt_view_keyboard(
    browse_filter_id: str | None,
    browse_category: Category,
    index: int,
    total: int,
    entry_filter_id: str,
    apt_id: int,
) -> InlineKeyboardMarkup:
    bfk = filter_key(browse_filter_id)
    bcat = browse_category.value
    rows: list[list[InlineKeyboardButton]] = []

    if total > 1:
        nav: list[InlineKeyboardButton] = []
        if index > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"anav:{bfk}:{bcat}:{index - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{index + 1} / {total}",
                callback_data="noop:page",
            )
        )
        if index < total - 1:
            nav.append(
                InlineKeyboardButton(
                    text="Вперёд ▶️",
                    callback_data=f"anav:{bfk}:{bcat}:{index + 1}",
                )
            )
        rows.append(nav)

    ef, aid = entry_filter_id, apt_id
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="✅", callback_data=_cat_cb(bfk, bcat, index, ef, aid, "good")
                ),
                InlineKeyboardButton(
                    text="🟡", callback_data=_cat_cb(bfk, bcat, index, ef, aid, "normal")
                ),
                InlineKeyboardButton(
                    text="❌", callback_data=_cat_cb(bfk, bcat, index, ef, aid, "bad")
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❓",
                    callback_data=_cat_cb(bfk, bcat, index, ef, aid, "unverified"),
                ),
                InlineKeyboardButton(
                    text="🗑", callback_data=_cat_cb(bfk, bcat, index, ef, aid, "deleted")
                ),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_keyboard_notify(
    entry_filter_id: str, apt_id: int
) -> InlineKeyboardMarkup:
    """Уведомления о новых — без листания."""
    ef, aid = entry_filter_id, apt_id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data=f"catn:{ef}:{aid}:good"),
                InlineKeyboardButton(text="🟡", callback_data=f"catn:{ef}:{aid}:normal"),
                InlineKeyboardButton(text="❌", callback_data=f"catn:{ef}:{aid}:bad"),
            ],
            [
                InlineKeyboardButton(text="❓", callback_data=f"catn:{ef}:{aid}:unverified"),
                InlineKeyboardButton(text="🗑", callback_data=f"catn:{ef}:{aid}:deleted"),
            ],
        ]
    )


def filters_list_keyboard(filters: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for flt in filters:
        fid = flt["id"]
        title = flt["title"][:40]
        rows.append(
            [
                InlineKeyboardButton(text=f"#{fid} {title}", callback_data=f"noop:{fid}"),
                InlineKeyboardButton(text="🗑", callback_data=f"fdel:{fid}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
