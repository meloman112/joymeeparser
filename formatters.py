from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import Category


def filter_key(filter_id: str | None) -> str:
    return filter_id or "all"


def viewed_label(viewed: bool | None) -> str:
    if viewed is True:
        return "👁 Смотрел"
    if viewed is False:
        return "👁‍🗨 Не смотрел"
    return "👁 ?"


def format_plain_card(
    data: dict[str, Any],
    *,
    is_new: bool = False,
    filter_title: str | None = None,
    viewed: bool | None = None,
    apt_category: Category | None = None,
    browse_category: Category | None = None,
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

    status_parts = [viewed_label(viewed)]
    if apt_category:
        status_parts.append(apt_category.label_ru)
    if browse_category and apt_category != browse_category:
        status_parts.append(f"лист: {browse_category.label_ru}")
    header += " · ".join(status_parts) + "\n"

    lines = [
        f"{price} <b> {title}</b>",
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
    *,
    viewed: bool = False,
) -> str:
    m = apt.get("map") or {}
    p = apt.get("plain") or {}
    apt_id = m.get("id") or p.get("id")
    price = m.get("price") or p.get("price")
    title = p.get("title", f"id {apt_id}")
    eye = "👁" if viewed else "○"
    return (
        f"{index + 1}. {eye} {category.label_ru} · <b>{price}</b> y.e. · {title[:38]}\n"
        f"   /apt_{filter_id}_{apt_id}"
    )


def _cat_cb(browse_fk: str, browse_cat: str, hint: int, entry_fid: str, apt_id: int, cat: str) -> str:
    return f"cat:{browse_fk}:{browse_cat}:{hint}:{entry_fid}:{apt_id}:{cat}"


def _view_cb(browse_fk: str, browse_cat: str, hint: int, entry_fid: str, apt_id: int, val: int) -> str:
    return f"view:{browse_fk}:{browse_cat}:{hint}:{entry_fid}:{apt_id}:{val}"


def _anav_cb(browse_fk: str, browse_cat: str, entry_fid: str, apt_id: int, direction: str, hint: int) -> str:
    return f"anav:{browse_fk}:{browse_cat}:{entry_fid}:{apt_id}:{direction}:{hint}"


def apt_view_keyboard(
    browse_filter_id: str | None,
    browse_category: Category,
    index: int,
    total: int,
    entry_filter_id: str,
    apt_id: int,
    *,
    viewed: bool = False,
) -> InlineKeyboardMarkup:
    bfk = filter_key(browse_filter_id)
    bcat = browse_category.value
    ef, aid, hint = entry_filter_id, apt_id, index
    rows: list[list[InlineKeyboardButton]] = []

    if total > 1:
        nav: list[InlineKeyboardButton] = []
        if index > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=_anav_cb(bfk, bcat, ef, aid, "p", hint),
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
                    callback_data=_anav_cb(bfk, bcat, ef, aid, "n", hint),
                )
            )
        rows.append(nav)

    viewed_on = 1 if viewed else 0
    rows.append(
        [
            InlineKeyboardButton(
                text="👁 Смотрел" if not viewed else "✓ Смотрел",
                callback_data=_view_cb(bfk, bcat, hint, ef, aid, 1),
            ),
            InlineKeyboardButton(
                text="Не смотрел",
                callback_data=_view_cb(bfk, bcat, hint, ef, aid, 0),
            ),
        ]
    )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="✅", callback_data=_cat_cb(bfk, bcat, hint, ef, aid, "good")
                ),
                InlineKeyboardButton(
                    text="🟡", callback_data=_cat_cb(bfk, bcat, hint, ef, aid, "normal")
                ),
                InlineKeyboardButton(
                    text="❌", callback_data=_cat_cb(bfk, bcat, hint, ef, aid, "bad")
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❓",
                    callback_data=_cat_cb(bfk, bcat, hint, ef, aid, "unverified"),
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=_cat_cb(bfk, bcat, hint, ef, aid, "deleted"),
                ),
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_keyboard_notify(entry_filter_id: str, apt_id: int) -> InlineKeyboardMarkup:
    ef, aid = entry_filter_id, apt_id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁", callback_data=f"viewn:{ef}:{aid}:1"),
                InlineKeyboardButton(text="○", callback_data=f"viewn:{ef}:{aid}:0"),
            ],
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
