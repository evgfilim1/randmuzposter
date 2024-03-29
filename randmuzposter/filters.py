__all__ = [
    "admin_filter",
]

from aiogram.types import CallbackQuery, Message

from .config import Config


def admin_filter(event: CallbackQuery | Message, config: Config) -> bool:
    if event.from_user is None:
        return False
    return event.from_user.id == config.admin
