import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot_handlers import router
from config import Settings
from joymi_api import JoymiClient
from media import close_media_client
from poller import ApartmentPoller
from storage import ApartmentStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings.from_env()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    store = ApartmentStore(settings.redis_url, settings.redis_password)
    api = JoymiClient()
    poller = ApartmentPoller(settings, bot, store, api)

    dp = Dispatcher()
    dp.include_router(router)
    dp.workflow_data.update(
        settings=settings,
        store=store,
        api=api,
        poller=poller,
    )

    await store.seed_notify_chats(settings.notify_chat_ids)
    poller.start()
    log.info("bot started, poll every %ss", settings.poll_interval_sec)

    try:
        await dp.start_polling(bot)
    finally:
        await poller.stop()
        await api.close()
        await close_media_client()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
