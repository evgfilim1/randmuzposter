__all__ = []

from asyncio import run

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware

from .config import Config
from .handlers import router
from .utils import SongLinkClient


async def _main():
    config = Config()
    client = SongLinkClient(user_country=config.user_country)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.message.middleware(ChatActionMiddleware())
    async with client:
        await dp.start_polling(
            Bot(config.token),
            client=client,
            config=config,
            allowed_updates=dp.resolve_used_update_types(),
        )


def main():
    run(_main())


main()
