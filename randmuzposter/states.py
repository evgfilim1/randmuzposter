__all__ = [
    "SongPostStates",
]

from aiogram.fsm.state import State, StatesGroup


class SongPostStates(StatesGroup):
    edit_wait = State()
    preparing = State()
    edit_song = State()
    edit = State()
