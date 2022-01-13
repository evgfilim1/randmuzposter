from __future__ import annotations

from asyncio import run
from functools import partial
from typing import overload

from aiogram import Bot, Dispatcher, F
from aiogram.dispatcher.filters.callback_data import CallbackData
from aiogram.dispatcher.fsm.context import FSMContext
from aiogram.dispatcher.fsm.state import StatesGroup, State
from aiogram.dispatcher.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendAudio, EditMessageText
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from httpx import AsyncClient
from yaml import safe_load

dp = Dispatcher(storage=MemoryStorage())

with open('config.yaml') as _f:
    config = safe_load(_f)


class EditCallback(CallbackData, prefix="edit"):
    what: str


class PostCallback(CallbackData, prefix="post"):
    notification: bool


class ActionCallback(CallbackData, prefix="action"):
    action: str


class SongPostStates(StatesGroup):
    edit_wait = State()
    preparing = State()
    edit_song = State()
    edit = State()


POST_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎶 Let the party begin!",
                          callback_data=PostCallback(notification=True).pack())],
    [InlineKeyboardButton(text="🔕 Post this silently",
                          callback_data=PostCallback(notification=False).pack())],
    # [InlineKeyboardButton(text="🎵 Replace file",
    #                       callback_data=EditCallback(what="song").pack())],  # TODO
    [InlineKeyboardButton(text="✏️ Edit YouTube link",
                          callback_data=EditCallback(what="yt_music").pack())],
    [InlineKeyboardButton(text="✏️ Edit Yandex link",
                          callback_data=EditCallback(what="yandex").pack())],
    [InlineKeyboardButton(text="✏️ Edit SoundCloud link",
                          callback_data=EditCallback(what="scloud").pack())],
    [InlineKeyboardButton(text="❌ Cancel",
                          callback_data=ActionCallback(action="delete").pack())],
])
FRIENDLY_NAMES = dict(
    spotify="Spotify",
    yt_music="YouTube Music",
    yandex="Yandex.Music",
    scloud="SoundCloud",
)
ADMIN_FILTER = F.from_user.id.in_(config['accept_from'])


@overload
def generate_audio_caption(
        *,
        spotify: str | None,
        yt_music: str | None,
        yandex: str | None,
        scloud: str | None,
) -> str:
    pass


def generate_audio_caption(**kwargs: str | None) -> str:
    text = ""
    for key, name in FRIENDLY_NAMES.items():
        if key in kwargs and kwargs[key] is not None:
            text += f'<a href="{kwargs[key]}">{name}</a>\n'
    return text


def extract_links(links: dict[str, dict[str, str]]) -> dict[str, str]:
    return {
        dest: links.get(src, {}).get("url")
        for src, dest
        in zip(("spotify", "youtubeMusic", "yandex", "soundcloud"), FRIENDLY_NAMES.keys())
    }


@dp.message(ADMIN_FILTER, F.audio.duration < 3, content_types=["audio"])
async def audio_first_seen(event: Message, state: FSMContext):
    await state.set_state(SongPostStates.edit_wait)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Continue anyway",
                              callback_data=ActionCallback(action="retry").pack())]
    ])
    m = await event.reply("⏳ Waiting for music to download…", reply_markup=kb)
    await state.update_data(message_id=m.message_id)


async def get_platform_links(client: AsyncClient, spotify_song_id: str) -> dict[str, str] | None:
    resp = await client.get(
        '/links',
        params=dict(platform='spotify', type='song', id=spotify_song_id),
    )
    if resp.status_code not in range(200, 300):
        print(resp.text)  # FIXME: use logging
        return None
    return extract_links(resp.json()["linksByPlatform"])


async def process_audio(
        message: Message,
        bot: Bot,
        state: FSMContext,
        client: AsyncClient,
) -> tuple[bool, str]:
    # find audio id
    for entity in (message.caption_entities or ()):
        if entity.type == "text_link" and entity.url.startswith(''):
            spotify_id = entity.url.rsplit('/', maxsplit=1)[1]
            break
    else:
        return False, "❌ No valid Spotify link found"

    # get platform links
    await bot.send_chat_action(message.chat.id, "upload_document")
    links = await get_platform_links(client, spotify_id)
    if links is None:
        return False, "❌ Error! Upstream returned an error. See logs for details."

    # messing with data
    file_id = message.audio.file_id
    await state.update_data(file_id=file_id, links=links, reply_to=message.message_id)

    return True, generate_audio_caption(**links)


@dp.callback_query(ADMIN_FILTER, ActionCallback.filter(F.action == "retry"))
@dp.edited_message(
    SongPostStates.edit_wait,
    ADMIN_FILTER,
    F.audio.duration >= 3,
    content_types=["audio"],
)
@dp.message(
    ADMIN_FILTER,
    F.audio.duration >= 3,
    content_types=["audio"],
    state=None,
)
async def handle_audio(
        event: CallbackQuery | Message,
        bot: Bot,
        state: FSMContext,
        client: AsyncClient,
):
    if isinstance(event, CallbackQuery):
        message = event.message.reply_to_message
        to_delete = event.message.message_id
        reply = event.message.edit_text
        await event.answer()
    else:
        message = event
        to_delete = (await state.get_data()).get("message_id")
        if to_delete is not None:
            # edited message
            reply = partial(EditMessageText, chat_id=event.chat.id, message_id=to_delete)
        else:
            # new message
            reply = event.reply
    ok, text = await process_audio(message, bot, state, client)
    if not ok:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Try again",
                                  callback_data=ActionCallback(action="retry").pack())]
        ])
        return reply(text=text, reply_markup=kb)

    await state.set_state(SongPostStates.preparing)
    data = await state.get_data()
    if to_delete is not None:
        await bot.delete_message(message.chat.id, to_delete)

    return message.reply_audio(
        data["file_id"],
        text,
        parse_mode="HTML",
        reply_markup=POST_KB,
    )


@dp.callback_query(SongPostStates.preparing, EditCallback.filter(), ADMIN_FILTER)
async def edit_link(query: CallbackQuery, callback_data: EditCallback, state: FSMContext):
    key = callback_data.what
    friendly_name = FRIENDLY_NAMES.get(key)
    if friendly_name is None:
        return query.answer(f"⁉️ Unknown platform {key!r}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Remove existing link",
                              callback_data=ActionCallback(action="pop_link").pack())],
    ])
    await query.message.edit_reply_markup()
    await state.set_state(SongPostStates.edit)
    m = await query.message.answer(
        f"🔗 Enter new link for <i>{friendly_name}</i>",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await state.update_data(
        key=key, prompt_msg=m.message_id, reply_to=query.message.reply_to_message.message_id
    )
    return query.answer()


async def update_link(
        new_value: str | None,
        state: FSMContext,
        chat_id: int,
        bot: Bot,
) -> SendAudio:
    data = await state.get_data()
    await bot.edit_message_reply_markup(chat_id, data["prompt_msg"])
    links = data["links"]
    links.update({data["key"]: new_value})
    await state.update_data(links=links)
    await state.set_state(SongPostStates.preparing)
    return SendAudio(
        chat_id=chat_id,
        audio=data["file_id"],
        caption=generate_audio_caption(**links),
        parse_mode="HTML",
        reply_to_message_id=data["reply_to"],
        reply_markup=POST_KB,
    )


@dp.callback_query(SongPostStates.edit, ActionCallback.filter(F.action == "pop_link"), ADMIN_FILTER)
async def pop_link(query: CallbackQuery, bot: Bot, state: FSMContext):
    return await update_link(None, state, query.message.chat.id, bot)


@dp.message(SongPostStates.edit, ADMIN_FILTER)
async def resend_with_edited(message: Message, bot: Bot, state: FSMContext):
    return await update_link(message.text, state, message.chat.id, bot)


@dp.callback_query(SongPostStates.preparing, PostCallback.filter(), ADMIN_FILTER)
async def post(query: CallbackQuery, callback_data: PostCallback, state: FSMContext):
    is_silent = callback_data.notification
    dest = str(config['post_to'])
    message = await query.message.copy_to(dest, disable_notification=is_silent)
    await state.clear()
    link_dest = dest.lstrip('@') if dest.startswith('@') else f"c/{dest.removeprefix('-100')}"
    await query.message.edit_caption(f"https://t.me/{link_dest}/{message.message_id}")
    return query.answer("📩{} Successfully posted!".format("🔕" if is_silent else "🔔"))


@dp.callback_query(ActionCallback.filter(F.action == "delete"))
async def nope(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_reply_markup()
    return query.answer("👌")


@dp.message(commands=["start", "help"])
async def hello(event: Message):
    return event.reply("👋 Hello! I can help you suggest new music to @evgenrandmuz! Simply send me"
                       " the name of the track or the track itself and I'll forward it.")


@dp.message(content_types=["text", "audio"])
async def fwd(message: Message):
    # now = datetime.utcnow()
    # if config["throttle"] \
    #         and last_msg.get(event.chat.id, datetime(1970, 1, 1)) + timedelta(minutes=1) > now:
    #     return message.reply("🐢 Can't send more than one message per minute, try again later")
    # last_msg[message.chat.id] = now
    await message.copy_to(chat_id=config['accept_from'][0])
    return message.reply("📩 Okay, I've forwarded it, thanks!")


async def main():
    client = AsyncClient(base_url='https://api.song.link/v1-alpha.1/')
    try:
        await dp.start_polling(Bot(config["token"]), client=client)
    finally:
        await client.aclose()


if __name__ == '__main__':
    run(main())
