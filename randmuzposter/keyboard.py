__all__ = [
    "Action",
    "ActionCallback",
    "EditCallback",
    "POST_KB",
    "PostCallback",
]

from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .constants import Service


class Action(Enum):
    RETRY = "retry"
    POP_LINK = "pop_link"
    CANCEL = "delete"


class EditCallback(CallbackData, prefix="edit"):
    what: Service | Literal["song"]


class PostCallback(CallbackData, prefix="post"):
    notification: bool


class ActionCallback(CallbackData, prefix="action"):
    action: Action


def _generate_post_kb() -> InlineKeyboardMarkup:
    builder = (
        InlineKeyboardBuilder()
        .button(text="🎶 Let the party begin!", callback_data=PostCallback(notification=True))
        .button(text="🔕 Post this silently", callback_data=PostCallback(notification=False))
        .button(text="🎵 Replace file", callback_data=EditCallback(what="song"))
    )
    for service in Service:
        builder.button(
            text=f"✏ Edit {service.value} link",
            callback_data=EditCallback(what=service),
        )
    # TODO: mark song as suggested
    builder.button(text="❌ Cancel", callback_data=ActionCallback(action=Action.CANCEL))
    return builder.adjust(1).as_markup()


POST_KB = _generate_post_kb()
