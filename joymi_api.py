from typing import Any

import httpx

from config import API_BASE


class JoymiClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_map_list(self, params: dict[str, str]) -> list[dict[str, Any]]:
        url = f"{API_BASE}/all-in-map-by-radius/"
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(body.get("message", "API error"))
        return body.get("results") or []

    async def fetch_plain(self, apt_id: int) -> dict[str, Any]:
        url = f"{API_BASE}/plain/{apt_id}/"
        resp = await self._client.get(url)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(body.get("message", "API error"))
        return body["results"]
