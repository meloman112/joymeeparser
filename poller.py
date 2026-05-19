import asyncio
import logging

from aiogram import Bot

from config import Settings
from formatters import category_keyboard_notify, format_plain_card
from joymi_api import JoymiClient
from media import send_apartment_card
from models import Category
from storage import ApartmentStore

log = logging.getLogger(__name__)


class ApartmentPoller:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        store: ApartmentStore,
        api: JoymiClient,
    ):
        self._settings = settings
        self._bot = bot
        self._store = store
        self._api = api
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_all(self, *, notify: bool = True) -> list[dict]:
        filters = await self._store.list_filters()
        if not filters:
            return []
        return [await self.run_filter(f["id"], notify=notify) for f in filters]

    async def run_filter(self, filter_id: str, *, notify: bool = True) -> dict:
        flt = await self._store.get_filter(filter_id)
        if not flt:
            return {"filter_id": filter_id, "error": "not found"}

        items = await self._api.fetch_map_list(flt["params"])
        active_ids = {x["id"] for x in items}
        first_run = not flt.get("initialized")
        new_ids = await self._store.register_new_for_filter(filter_id, list(active_ids))

        stats = {
            "filter_id": filter_id,
            "title": flt["title"],
            "fetched": len(items),
            "new": len(new_ids),
            "gone": 0,
            "first_run": first_run,
        }

        for item in items:
            apt_id = item["id"]
            await self._store.save_apartment(apt_id, map_data=item)
            if apt_id in new_ids:
                await self._store.mark_known(filter_id, apt_id, category=Category.UNVERIFIED)

        stats["gone"] = len(await self._store.mark_missing_as_deleted(filter_id, active_ids))
        await self._store.set_last_active(filter_id, active_ids)

        if first_run:
            await self._store.set_filter_initialized(filter_id)
            log.info("filter %s seeded %s apts", filter_id, len(active_ids))
        elif notify and new_ids:
            chats = await self._store.get_notify_chats()
            if not chats:
                chats = set(self._settings.notify_chat_ids)
            for apt_id in new_ids:
                await self._notify_new(filter_id, flt["title"], apt_id, chats)

        return stats

    async def _notify_new(
        self, filter_id: str, filter_title: str, apt_id: int, chats: set[int]
    ) -> None:
        try:
            plain = await self._api.fetch_plain(apt_id)
        except Exception:
            log.exception("plain fetch %s", apt_id)
            return

        await self._store.save_apartment(apt_id, plain_data=plain)
        text = format_plain_card(plain, is_new=True, filter_title=filter_title)
        kb = category_keyboard_notify(filter_id, apt_id)

        for chat_id in chats:
            try:
                await send_apartment_card(
                    self._bot,
                    chat_id,
                    plain,
                    text=text,
                    reply_markup=kb,
                )
            except Exception as e:
                log.warning("notify chat %s: %s", chat_id, e)

    async def _loop(self) -> None:
        while True:
            try:
                results = await self.run_all(notify=True)
                log.info("poll ok: %s filters", len(results))
            except Exception:
                log.exception("poll failed")
            await asyncio.sleep(self._settings.poll_interval_sec)
