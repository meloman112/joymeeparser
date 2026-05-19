import json
import uuid
from typing import Any

import redis.asyncio as redis

from models import Category


class ApartmentStore:
    PREFIX = "joyme"
    KEY_FILTERS = f"{PREFIX}:filters:all"
    KEY_NOTIFY = f"{PREFIX}:notify_chats"

    def __init__(self, redis_url: str, redis_password: str | None = None):
        self._r: redis.Redis = redis.from_url(
            redis_url,
            decode_responses=True,
            password=redis_password or None,
        )

    async def close(self) -> None:
        await self._r.aclose()

    # --- filters ---

    def _filter_key(self, filter_id: str) -> str:
        return f"{self.PREFIX}:filter:{filter_id}"

    def _filter_prefix(self, filter_id: str) -> str:
        return f"{self.PREFIX}:f:{filter_id}"

    async def add_filter(self, data: dict[str, Any], chat_id: int) -> dict[str, Any]:
        filter_id = uuid.uuid4().hex[:8]
        record = {
            "id": filter_id,
            "url": data["url"],
            "params": data["params"],
            "title": data["title"],
            "endpoint": data.get("endpoint", "all-in-map-by-radius"),
            "chat_id": chat_id,
            "initialized": False,
        }
        await self._r.set(self._filter_key(filter_id), json.dumps(record, ensure_ascii=False))
        await self._r.sadd(self.KEY_FILTERS, filter_id)
        return record

    async def get_filter(self, filter_id: str) -> dict[str, Any] | None:
        raw = await self._r.get(self._filter_key(filter_id))
        return json.loads(raw) if raw else None

    async def list_filters(self) -> list[dict[str, Any]]:
        ids = await self._r.smembers(self.KEY_FILTERS)
        out: list[dict[str, Any]] = []
        for fid in sorted(ids):
            flt = await self.get_filter(fid)
            if flt:
                out.append(flt)
        return out

    async def delete_filter(self, filter_id: str) -> bool:
        if not await self._r.sismember(self.KEY_FILTERS, filter_id):
            return False
        pattern = f"{self._filter_prefix(filter_id)}:*"
        async for key in self._r.scan_iter(match=pattern):
            await self._r.delete(key)
        await self._r.delete(self._filter_key(filter_id))
        await self._r.srem(self.KEY_FILTERS, filter_id)
        return True

    async def set_filter_initialized(self, filter_id: str) -> None:
        flt = await self.get_filter(filter_id)
        if not flt:
            return
        flt["initialized"] = True
        await self._r.set(self._filter_key(filter_id), json.dumps(flt, ensure_ascii=False))

    def _f_known(self, filter_id: str) -> str:
        return f"{self._filter_prefix(filter_id)}:known"

    def _f_last_active(self, filter_id: str) -> str:
        return f"{self._filter_prefix(filter_id)}:last_active"

    def _f_idx_key(self, filter_id: str, cat: Category) -> str:
        return f"{self._filter_prefix(filter_id)}:idx:{cat.value}"

    def _f_apt_meta(self, filter_id: str, apt_id: int) -> str:
        return f"{self._filter_prefix(filter_id)}:meta:{apt_id}"

    # --- apartments (global plain/map) ---

    def _apt_key(self, apt_id: int) -> str:
        return f"{self.PREFIX}:apt:{apt_id}"

    async def get_apartment(self, apt_id: int) -> dict[str, Any] | None:
        raw = await self._r.get(self._apt_key(apt_id))
        return json.loads(raw) if raw else None

    async def save_apartment(
        self,
        apt_id: int,
        *,
        map_data: dict[str, Any] | None = None,
        plain_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_apartment(apt_id) or {}
        if map_data:
            existing["map"] = map_data
        if plain_data:
            existing["plain"] = plain_data
        await self._r.set(self._apt_key(apt_id), json.dumps(existing, ensure_ascii=False))
        return existing

    async def get_category(self, filter_id: str, apt_id: int) -> Category:
        raw = await self._r.get(self._f_apt_meta(filter_id, apt_id))
        if raw:
            return Category(json.loads(raw).get("category", Category.UNVERIFIED.value))
        return Category.UNVERIFIED

    async def set_category(self, filter_id: str, apt_id: int, category: Category) -> bool:
        if not await self._r.sismember(self._f_known(filter_id), apt_id):
            return False
        old = await self.get_category(filter_id, apt_id)
        if old != category:
            await self._r.srem(self._f_idx_key(filter_id, old), apt_id)
        await self._r.sadd(self._f_idx_key(filter_id, category), apt_id)
        await self._r.set(
            self._f_apt_meta(filter_id, apt_id),
            json.dumps({"category": category.value}, ensure_ascii=False),
        )
        return True

    async def register_new_for_filter(self, filter_id: str, ids: list[int]) -> list[int]:
        new_ids: list[int] = []
        for apt_id in ids:
            if not await self._r.sismember(self._f_known(filter_id), apt_id):
                new_ids.append(apt_id)
        return new_ids

    async def mark_known(self, filter_id: str, apt_id: int, *, category: Category | None = None) -> None:
        await self._r.sadd(self._f_known(filter_id), apt_id)
        cat = category or Category.UNVERIFIED
        await self._r.sadd(self._f_idx_key(filter_id, cat), apt_id)
        await self._r.set(
            self._f_apt_meta(filter_id, apt_id),
            json.dumps({"category": cat.value}, ensure_ascii=False),
        )

    async def get_last_active(self, filter_id: str) -> set[int]:
        raw = await self._r.smembers(self._f_last_active(filter_id))
        return {int(x) for x in raw}

    async def set_last_active(self, filter_id: str, ids: set[int]) -> None:
        key = self._f_last_active(filter_id)
        await self._r.delete(key)
        if ids:
            await self._r.sadd(key, *ids)

    async def list_entries(
        self,
        filter_id: str | None,
        category: Category,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[str, int]], int]:
        """(filter_id, apt_id) с пагинацией. filter_id=None — все фильтры."""
        if filter_id:
            filter_ids = [filter_id]
        else:
            filter_ids = [f["id"] for f in await self.list_filters()]

        entries: list[tuple[str, int]] = []
        for fid in filter_ids:
            ids = await self._r.smembers(self._f_idx_key(fid, category))
            for apt_id in ids:
                entries.append((fid, int(apt_id)))

        entries.sort(key=lambda x: x[1], reverse=True)
        total = len(entries)
        return entries[offset : offset + limit], total

    async def count_by_category(self, filter_id: str, category: Category) -> int:
        return await self._r.scard(self._f_idx_key(filter_id, category))

    async def count_known(self, filter_id: str) -> int:
        return await self._r.scard(self._f_known(filter_id))

    async def mark_missing_as_deleted(self, filter_id: str, active_ids: set[int]) -> list[int]:
        last = await self.get_last_active(filter_id)
        gone = last - active_ids
        moved: list[int] = []
        for apt_id in gone:
            cat = await self.get_category(filter_id, apt_id)
            if cat == Category.DELETED:
                continue
            await self.set_category(filter_id, apt_id, Category.DELETED)
            moved.append(apt_id)
        return moved

    async def get_notify_chats(self) -> set[int]:
        return {int(x) for x in await self._r.smembers(self.KEY_NOTIFY)}

    async def add_notify_chat(self, chat_id: int) -> None:
        await self._r.sadd(self.KEY_NOTIFY, chat_id)

    async def remove_notify_chat(self, chat_id: int) -> None:
        await self._r.srem(self.KEY_NOTIFY, chat_id)

    async def seed_notify_chats(self, chat_ids: list[int]) -> None:
        if chat_ids:
            await self._r.sadd(self.KEY_NOTIFY, *chat_ids)

    def _card_msgs_key(self, chat_id: int) -> str:
        return f"{self.PREFIX}:chat:{chat_id}:card_msgs"

    async def pop_card_message_ids(self, chat_id: int) -> list[int]:
        key = self._card_msgs_key(chat_id)
        raw = await self._r.get(key)
        await self._r.delete(key)
        if not raw:
            return []
        return json.loads(raw)

    async def set_card_message_ids(self, chat_id: int, message_ids: list[int]) -> None:
        await self._r.set(
            self._card_msgs_key(chat_id),
            json.dumps(message_ids),
        )
