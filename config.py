import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    redis_url: str
    redis_password: str
    notify_chat_ids: list[int]
    poll_interval_sec: int

    @classmethod
    def from_env(cls) -> "Settings":
        raw_ids = os.getenv("NOTIFY_CHAT_IDS", "").strip()
        chat_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip()]

        token = os.getenv("BOT_TOKEN", "")
        if not token:
            raise RuntimeError("BOT_TOKEN не задан в .env")

        return cls(
            bot_token=token,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            redis_password=os.getenv("REDIS_PASSWORD", "") or None,
            notify_chat_ids=chat_ids,
            poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "1800")),
        )


API_BASE = "https://api.joymi.uz/api/v1/announcement"
