from asyncio import run
from datetime import datetime, timedelta
from typing import Any, Union, Optional

from aiogram import Bot, Dispatcher
from aiogram.api.methods import TelegramMethod, Request
from aiogram.api.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, \
    TelegramObject
from aiogram.utils.exceptions import TelegramAPIError
from httpx import AsyncClient

from config import ACCEPT_FROM, POST_TO, THROTTLE, TOKEN

dp = Dispatcher()
states: dict[int, dict[str, Any]] = {}
last_msg: dict[int, datetime] = {}
client = AsyncClient(base_url='https://api.song.link/v1-alpha.1/')

POST_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎶 Let the party begin!", callback_data="post")],
    [InlineKeyboardButton(text="🔕 Post this silently", callback_data="post_silent")],
    [InlineKeyboardButton(text="✋ I'll do it myself", callback_data="delete")],
    [InlineKeyboardButton(text="✏️ Edit YouTube Link", callback_data="edit_yt_music")],
    [InlineKeyboardButton(text="✏️ Edit Yandex link", callback_data="edit_yandex")],
    [InlineKeyboardButton(text="✏️ Edit SoundCloud link", callback_data="edit_scloud")],
])
FRIENDLY_NAMES = dict(
    spotify="Spotify",
    yt_music="YouTube Music",
    yandex="Yandex.Music",
    scloud="SoundCloud",
)


def accept_only_from_me(e: Union[Message, CallbackQuery]):
    return e.from_user.id == ACCEPT_FROM


class MessageId(TelegramObject):
    message_id: int


class CopyMessage(TelegramMethod[MessageId]):
    __returning__ = MessageId

    chat_id: Union[int, str]
    from_chat_id: Union[int, str]
    message_id: int
    disable_notification: Optional[bool] = None

    def build_request(self, bot: Bot) -> Request:
        data = self.dict()
        return Request(method="copyMessage", data=data)


def gen_text(
        *,
        spotify: Optional[str],
        yt_music: Optional[str],
        yandex: Optional[str],
        scloud: Optional[str],
) -> str:
    text = ""
    if spotify is not None:
        text += f'<a href="{spotify}">Spotify</a>\n'
    if yt_music is not None:
        text += f'<a href="{yt_music}">YouTube Music</a>\n'
    if yandex is not None:
        text += f'<a href="{yandex}">Yandex.Music</a>\n'
    if scloud is not None:
        text += f'<a href="{scloud}">SoundCloud</a>\n'
    return text


def extract_links(links: dict[str, dict[str, str]]) -> dict[str, str]:
    return dict(
        spotify=links.get("spotify", {}).get("url"),
        yt_music=links.get("youtubeMusic", {}).get("url"),
        yandex=links.get("yandex", {}).get("url"),
        scloud=links.get("soundcloud", {}).get("url"),
    )


@dp.message(commands=["start", "help"])
async def hello(event: Message):
    await event.reply("👋 Hello! I can help you suggest new music to @evgenrandmuz! Simply send me"
                      " the name of the track or the track itself and I'll forward it.")


@dp.message(accept_only_from_me, content_types=["audio"])
async def audio_first_seen(event: Message):
    state = states[event.chat.id] = {}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Already", callback_data="handle")],
    ])
    m = await event.reply("⏳ Waiting for this message to be edited…", reply_markup=kb)
    state["message_id"] = m.message_id


@dp.callback_query(text="handle")
@dp.edited_message(accept_only_from_me, content_types=["audio"])
async def handle_audio(event: Union[Message, CallbackQuery], bot: Bot):
    orig_event = event
    if isinstance(event, CallbackQuery):
        event = event.message.reply_to_message
    if (state := states.get(event.chat.id)) is None:
        if isinstance(orig_event, CallbackQuery):
            await orig_event.answer("⁉")
            await bot.edit_message_reply_markup(event.chat.id, orig_event.message.message_id)
        return
    file_id = state["file_id"] = event.audio.file_id
    for entity in event.caption_entities:
        if entity.type == "text_link" and entity.url.startswith('https://song.link/s/'):
            id_ = entity.url.rsplit('/', maxsplit=1)[1]
            break
    else:
        await bot.edit_message_text("❌ Error! No suitable link found!", event.chat.id,
                                    state["message_id"])
        del states[event.chat.id]
        return
    await bot.send_chat_action(event.chat.id, "upload_document")
    resp = await client.get('/links', params=dict(platform='spotify', type='song', id=id_))
    if resp.status_code not in range(200, 300):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Try again", callback_data="handle")]
        ])
        try:
            await bot.edit_message_text(
                f"❌ Error! Upstream returned an error: <code>{resp.text}</code>",
                event.chat.id, state["message_id"], parse_mode="HTML", reply_markup=kb,
            )
            return 
        except TelegramAPIError as e:
            if 'not modified' not in str(e):
                raise
    api_resp = resp.json()
    links = state["links"] = extract_links(api_resp["linksByPlatform"])
    text = gen_text(**links)

    await event.reply_audio(file_id, text, parse_mode="HTML", reply_markup=POST_KB)
    await bot.delete_message(event.chat.id, state.pop("message_id"))
    # del states[event.chat.id]


@dp.message(lambda m: states.get(m.chat.id, {}).get("svc") is not None, accept_only_from_me)
async def resend_with_edited(event: Message, bot: Bot):
    state = states[event.chat.id]
    await bot.edit_message_reply_markup(event.chat.id, state["link_msg"])
    links = state["links"]
    links.update({state["svc"]: event.text})
    text = gen_text(**links)
    await event.reply_audio(state["file_id"], text, parse_mode="HTML", reply_markup=POST_KB)


@dp.message(content_types=["text", "audio"])
async def fwd(event: Message, bot: Bot):
    if last_msg.get(event.chat.id, datetime(1970, 1, 1)) + timedelta(minutes=1) > datetime.utcnow()\
            and THROTTLE:
        await event.reply("🐢 Can't send more than one message per minute, try again later")
        return
    await bot(CopyMessage(chat_id=ACCEPT_FROM, from_chat_id=event.chat.id,
                          message_id=event.message_id))
    last_msg[event.chat.id] = datetime.utcnow()
    await event.reply("📩 Okay, I've forwarded it, thanks!")


@dp.callback_query(lambda q: q.data.startswith("post"), accept_only_from_me)
async def post(query: CallbackQuery, bot: Bot):
    silent = query.data.endswith("silent")
    m = await bot(CopyMessage(chat_id=POST_TO, from_chat_id=query.message.chat.id,
                              message_id=query.message.message_id, disable_notification=silent))
    await query.answer("📩 Successfully posted! {}".format("🔕" if silent else "🔔"))
    await bot.edit_message_caption(query.message.chat.id, query.message.message_id,
                                   caption=f"https://t.me/{POST_TO.lstrip('@')}/{m.message_id}")
    del states[query.message.chat.id]


@dp.callback_query(lambda q: q.data.startswith("edit"), accept_only_from_me)
async def edit_link(query: CallbackQuery, bot: Bot):
    if (state := states.get(query.message.chat.id)) is None:
        await query.answer("⁉️")
        return
    svc = query.data.split('_', maxsplit=1)[1]
    # state["message_id"] = query.message.message_id
    state["svc"] = svc
    svc_friendly = FRIENDLY_NAMES.get(svc)
    if svc_friendly is None:
        await query.answer(f"⁉️ Unknown platform {svc}")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Remove existing link", callback_data="pop")],
    ])
    await query.answer()
    await bot.edit_message_reply_markup(query.message.chat.id, query.message.message_id)
    m = await bot.send_message(query.message.chat.id,
                               f"🔗 Enter new link for <i>{svc_friendly}</i>",
                               parse_mode="HTML", reply_markup=kb)
    state["link_msg"] = m.message_id


@dp.callback_query(lambda q: q.data.startswith("pop"), accept_only_from_me)
async def pop_link(query: CallbackQuery, bot: Bot):
    if (state := states.get(query.message.chat.id)) is None:
        await query.answer("⁉️")
        return
    await bot.edit_message_reply_markup(query.message.chat.id, state["link_msg"])
    links = state["links"]
    links.update({state["svc"]: None})
    text = gen_text(**links)
    await query.message.answer_audio(state["file_id"], text, parse_mode="HTML",
                                     reply_markup=POST_KB)


@dp.callback_query(text="delete")
async def nope(query: CallbackQuery, bot: Bot):
    await query.answer("👌")
    await bot.edit_message_reply_markup(query.message.chat.id, query.message.message_id)
    del states[query.message.chat.id]


async def main():
    try:
        await dp.start_polling(Bot(TOKEN))
    finally:
        await client.aclose()


if __name__ == '__main__':
    try:
        run(main())
    except (KeyboardInterrupt, SystemExit):
        pass  # don't show traceback
