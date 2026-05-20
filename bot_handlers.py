import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from apt_browser import navigate_apt, show_apt_by_ids, show_apt_entry
from formatters import category_keyboard_notify, filters_list_keyboard
from list_browser import CATEGORIES, parse_list_args, send_list_page
from joymi_api import JoymiClient
from media import send_apartment_card
from models import Category
from poller import ApartmentPoller
from storage import ApartmentStore
from url_parser import parse_filter_url

router = Router()

URL_RE = re.compile(r"https?://", re.I)


@router.message(Command("start"))
async def cmd_start(msg: Message, store: ApartmentStore):
    await store.add_notify_chat(msg.chat.id)
    await msg.answer(
        "Пришли <b>ссылку</b> на API Joymi с параметрами — добавлю фильтр.\n\n"
        "Пример:\n"
        "<code>https://api.joymi.uz/api/v1/announcement/all-in-map-by-radius/"
        "?entity_purpose=long_term_rent&...</code>\n\n"
        "/filters — список и удаление\n"
        "/scan — обновить все фильтры\n"
        "/scan abc12345 — один фильтр\n"
        "/stats — статистика\n"
        "/list — все непроверенные (листать кнопками)\n"
        "/list good · /list abc12345 bad\n"
        "/apt_abc12345_196886 — карточка + все фото\n"
        "/notify_on /notify_off",
        parse_mode="HTML",
    )


@router.message(F.text & F.text.regexp(URL_RE))
async def on_filter_url(msg: Message, store: ApartmentStore, poller: ApartmentPoller):
    try:
        parsed = parse_filter_url(msg.text or "")
    except ValueError as e:
        await msg.answer(str(e))
        return

    flt = await store.add_filter(parsed, msg.chat.id)
    await msg.answer(
        f"✅ Фильтр <b>#{flt['id']}</b>\n{flt['title']}\n\nПервый опрос…",
        parse_mode="HTML",
    )
    stats = await poller.run_filter(flt["id"], notify=False)
    await msg.answer(
        f"Сохранено {stats['fetched']} квартир. Новых: {stats['new']}\n"
        f"Дальше проверка каждые 30 мин, пуши только о новых.",
    )


@router.message(Command("filters"))
async def cmd_filters(msg: Message, store: ApartmentStore):
    filters = await store.list_filters()
    if not filters:
        await msg.answer("Фильтров нет — пришли ссылку")
        return
    lines = ["<b>Фильтры</b> (🗑 удалить):\n"]
    for flt in filters:
        n = await store.count_known(flt["id"])
        lines.append(f"#{flt['id']} · {flt['title']} · {n} шт")
    await msg.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=filters_list_keyboard(filters),
    )


@router.callback_query(F.data.startswith("fdel:"))
async def on_filter_delete(cb: CallbackQuery, store: ApartmentStore):
    filter_id = cb.data.split(":", 1)[1]
    ok = await store.delete_filter(filter_id)
    await cb.answer("Удалён" if ok else "Не найден", show_alert=not ok)
    if cb.message and ok:
        filters = await store.list_filters()
        if filters:
            lines = ["<b>Фильтры</b>:\n"] + [
                f"#{f['id']} · {f['title']}" for f in filters
            ]
            await cb.message.edit_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=filters_list_keyboard(filters),
            )
        else:
            await cb.message.edit_text("Фильтров не осталось")


@router.callback_query(F.data.startswith("noop:"))
async def on_noop(cb: CallbackQuery):
    await cb.answer()


@router.message(Command("notify_on"))
async def notify_on(msg: Message, store: ApartmentStore):
    await store.add_notify_chat(msg.chat.id)
    await msg.answer("Уведомления включены")


@router.message(Command("notify_off"))
async def notify_off(msg: Message, store: ApartmentStore):
    await store.remove_notify_chat(msg.chat.id)
    await msg.answer("Уведомления выключены")


@router.message(Command("scan"))
async def cmd_scan(msg: Message, command: CommandObject, poller: ApartmentPoller):
    arg = (command.args or "").strip()
    await msg.answer("Сканирую…")
    if arg:
        stats = await poller.run_filter(arg, notify=True)
        if stats.get("error"):
            await msg.answer("Фильтр не найден")
            return
        await msg.answer(
            f"#{stats['filter_id']}: {stats['fetched']} шт, новых {stats['new']}, "
            f"снято {stats['gone']}"
        )
    else:
        results = await poller.run_all(notify=True)
        if not results:
            await msg.answer("Нет фильтров — пришли ссылку")
            return
        lines = [
            f"#{r['filter_id']}: +{r['new']} / {r['fetched']}" for r in results
        ]
        await msg.answer("Готово:\n" + "\n".join(lines))


@router.message(Command("stats"))
async def cmd_stats(msg: Message, store: ApartmentStore):
    filters = await store.list_filters()
    if not filters:
        await msg.answer("Нет фильтров")
        return
    for flt in filters:
        fid = flt["id"]
        lines = [f"<b>#{fid}</b> {flt['title']}"]
        for cat in Category:
            n = await store.count_by_category(fid, cat)
            lines.append(f"  {cat.label_ru}: {n}")
        lines.append(f"  всего: {await store.count_known(fid)}")
        await msg.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("list"))
async def cmd_list(msg: Message, command: CommandObject, store: ApartmentStore):
    parts = (command.args or "").split()
    filter_ids = {f["id"] for f in await store.list_filters()}

    if not filter_ids:
        await msg.answer("Нет фильтров — пришли ссылку")
        return

    try:
        filter_id, cat = parse_list_args(parts, filter_ids)
    except ValueError:
        cats = ", ".join(sorted(CATEGORIES))
        await msg.answer(
            f"/list — все непроверенные\n"
            f"/list <code>filter_id</code> [{cats}]\n"
            f"/list good — категория по всем фильтрам",
            parse_mode="HTML",
        )
        return

    if filter_id and filter_id not in filter_ids:
        await msg.answer("Фильтр не найден")
        return

    await send_list_page(msg, store, filter_id, cat, page=0)


@router.callback_query(F.data.startswith("lst:"))
async def on_list_scroll(cb: CallbackQuery, store: ApartmentStore):
    _, fk, cat_s, page_s = cb.data.split(":", 3)
    try:
        cat = Category(cat_s)
        page = int(page_s)
    except (ValueError, KeyError):
        await cb.answer("Ошибка")
        return

    filter_id = None if fk == "all" else fk
    if filter_id and not await store.get_filter(filter_id):
        await cb.answer("Фильтр удалён", show_alert=True)
        return

    await send_list_page(cb, store, filter_id, cat, page=page, edit=True)


@router.message(F.text.regexp(r"^/apt_([a-f0-9]+)_(\d+)$"))
async def cmd_apt(msg: Message, store: ApartmentStore, api: JoymiClient):
    m = re.match(r"^/apt_([a-f0-9]+)_(\d+)$", msg.text or "")
    filter_id, apt_id = m.group(1), int(m.group(2))

    if not await store.get_filter(filter_id):
        await msg.answer("Фильтр не найден")
        return

    await show_apt_by_ids(msg, store, api, filter_id, apt_id)


@router.callback_query(F.data.startswith("open:"))
async def on_apt_open(cb: CallbackQuery, store: ApartmentStore, api: JoymiClient):
    _, fk, cat_s, idx_s = cb.data.split(":", 3)
    browse_filter_id = None if fk == "all" else fk
    try:
        category = Category(cat_s)
        index = int(idx_s)
        entries, _ = await store.list_entries(browse_filter_id, category, index, 1)
        if not entries:
            await cb.answer("Пусто", show_alert=True)
            return
        entry_fid, apt_id = entries[0]
        await show_apt_entry(
            cb,
            store,
            api,
            browse_filter_id=browse_filter_id,
            browse_category=category,
            entry_fid=entry_fid,
            apt_id=apt_id,
            hint_index=index,
        )
    except (ValueError, KeyError):
        await cb.answer("Ошибка")


@router.callback_query(F.data.startswith("anav:"))
async def on_apt_nav(cb: CallbackQuery, store: ApartmentStore, api: JoymiClient):
    parts = cb.data.split(":")
    if len(parts) != 7:
        await cb.answer("Устаревшая кнопка — открой заново")
        return
    _, fk, cat_s, entry_fid, apt_id_s, dir_s, hint_s = parts
    browse_filter_id = None if fk == "all" else fk
    try:
        direction = {"n": "next", "p": "prev"}[dir_s]
        await navigate_apt(
            cb,
            store,
            api,
            browse_filter_id=browse_filter_id,
            browse_category=Category(cat_s),
            entry_fid=entry_fid,
            apt_id=int(apt_id_s),
            direction=direction,
            hint_index=int(hint_s),
        )
    except (ValueError, KeyError):
        await cb.answer("Ошибка")


@router.callback_query(F.data.startswith("view:"))
async def on_viewed(cb: CallbackQuery, store: ApartmentStore, api: JoymiClient):
    parts = cb.data.split(":")
    if len(parts) != 7:
        await cb.answer("Устаревшая кнопка")
        return
    _, browse_fk, browse_cat, hint_s, entry_fid, apt_id_s, val_s = parts
    browse_filter_id = None if browse_fk == "all" else browse_fk
    apt_id = int(apt_id_s)
    viewed = val_s == "1"

    ok = await store.set_viewed(entry_fid, apt_id, viewed)
    if not ok:
        await cb.answer("Нет в фильтре", show_alert=True)
        return

    await cb.answer("Смотрел" if viewed else "Не смотрел")
    await navigate_apt(
        cb,
        store,
        api,
        browse_filter_id=browse_filter_id,
        browse_category=Category(browse_cat),
        entry_fid=entry_fid,
        apt_id=apt_id,
        direction="stay",
        hint_index=int(hint_s),
    )


@router.callback_query(F.data.startswith("viewn:"))
async def on_viewed_notify(cb: CallbackQuery, store: ApartmentStore):
    _, entry_fid, apt_id_s, val_s = cb.data.split(":", 3)
    viewed = val_s == "1"
    ok = await store.set_viewed(entry_fid, int(apt_id_s), viewed)
    await cb.answer("Смотрел" if viewed and ok else ("Не смотрел" if ok else "Ошибка"))


@router.callback_query(F.data.startswith("cat:"))
async def on_category(cb: CallbackQuery, store: ApartmentStore, api: JoymiClient):
    parts = cb.data.split(":")
    if len(parts) != 7:
        await cb.answer("Устаревшая кнопка — открой квартиру заново")
        return

    _, browse_fk, browse_cat, hint_s, entry_fid, apt_id_s, cat_s = parts
    apt_id = int(apt_id_s)
    cat = Category(cat_s)
    browse_filter_id = None if browse_fk == "all" else browse_fk
    browse_category = Category(browse_cat)
    hint_index = int(hint_s)

    ok = await store.set_category(entry_fid, apt_id, cat)
    if not ok:
        await cb.answer("Нет в этом фильтре", show_alert=True)
        return

    await cb.answer(cat.label_ru)
    await navigate_apt(
        cb,
        store,
        api,
        browse_filter_id=browse_filter_id,
        browse_category=browse_category,
        entry_fid=entry_fid,
        apt_id=apt_id,
        direction="stay",
        hint_index=hint_index,
    )


@router.callback_query(F.data.startswith("catn:"))
async def on_category_notify(cb: CallbackQuery, store: ApartmentStore):
    _, entry_fid, apt_id_s, cat_s = cb.data.split(":", 3)
    apt_id = int(apt_id_s)
    cat = Category(cat_s)

    ok = await store.set_category(entry_fid, apt_id, cat)
    if not ok:
        await cb.answer("Нет в фильтре", show_alert=True)
        return

    await cb.answer(cat.label_ru)
    if cb.message:
        await cb.message.edit_reply_markup(
            reply_markup=category_keyboard_notify(entry_fid, apt_id)
        )
