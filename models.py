from enum import StrEnum
from typing import Any


class Category(StrEnum):
    GOOD = "good"           # хороший
    NORMAL = "normal"       # нормальный
    BAD = "bad"             # плохой
    UNVERIFIED = "unverified"  # не проверенный
    DELETED = "deleted"     # удаленный

    @property
    def label_ru(self) -> str:
        return {
            Category.GOOD: "✅ Хороший",
            Category.NORMAL: "🟡 Нормальный",
            Category.BAD: "❌ Плохой",
            Category.UNVERIFIED: "❓ Не проверенный",
            Category.DELETED: "🗑 Удалённый",
        }[self]


def short_apt(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data["id"],
        "price": data.get("price"),
        "currency": data.get("currency"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
    }
