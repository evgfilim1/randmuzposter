__all__ = [
    "router",
]

import asyncio
import logging

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.methods import SendAudio
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config
from .constants import Service
from .filters import admin_filter
from .keyboard import Action, POST_KB, ActionCallback, EditCallback, PostCallback
from .states import SongPostStates
from .utils import (
    AudioProcessingError,
    SongLinkClient,
    generate_audio_caption,
    process_audio,
    suggested_track_text,
)

router = Router()


@router.message(admin_filter, F.audio.duration < 3)
async def audio_first_seen(event: Message, state: FSMContext):
    await state.set_state(SongPostStates.edit_wait)
    kb = (
        InlineKeyboardBuilder()
        .button(
            text="⏩ Continue anyway",
            callback_data=ActionCallback(action=Action.RETRY),
        )
        .button(
            text="❌ Cancel",
            callback_data=ActionCallback(action=Action.CANCEL),
        )
        .adjust(1)
        .as_markup()
    )
    m = await event.reply("⏳ Waiting for music to download…", reply_markup=kb)
    await state.update_data(message_id=m.message_id)


@router.callback_query(
    admin_filter,
    ActionCallback.filter(F.action == Action.RETRY),
)
async def handle_retry(
    query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    client: SongLinkClient,
):
    async with ChatActionSender(chat_id=query.message.chat.id, action="upload_audio", bot=bot):
        res = await handle_audio_common(query.message.reply_to_message, state, client)
        if isinstance(res, dict):
            return query.message.edit_text(**res)
        await asyncio.gather(bot(query.answer()), bot(query.message.delete()))
        return res


@router.edited_message(
    admin_filter,
    SongPostStates.edit_wait,
    F.audio.duration >= 3,
    flags={"chat_action": "upload_audio"},
)
async def handle_downloaded(
    message: Message,
    state: FSMContext,
    bot: Bot,
    client: SongLinkClient,
):
    res = await handle_audio_common(message, state, client)
    if isinstance(res, dict):
        return message.edit_text(**res)
    data = await state.get_data()
    await bot.delete_message(message.chat.id, data["message_id"])
    return res


@router.message(
    admin_filter,
    default_state,
    F.audio.duration >= 3,
    flags={"chat_action": "upload_audio"},
)
async def handle_audio(
    message: Message,
    state: FSMContext,
    client: SongLinkClient,
):
    return await handle_audio_common(message, state, client)


async def handle_audio_common(
    message: Message,
    state: FSMContext,
    client: SongLinkClient,
) -> dict[str, str | InlineKeyboardMarkup] | SendAudio:
    try:
        links = await process_audio(message.caption, message.caption_entities, client)
    except AudioProcessingError as e:
        kb = (
            InlineKeyboardBuilder()
            .button(
                text="🔁 Try again",
                callback_data=ActionCallback(action=Action.RETRY),
            )
            .button(
                text="❌ Cancel",
                callback_data=ActionCallback(action=Action.CANCEL),
            )
            .adjust(1)
            .as_markup()
        )
        if isinstance(e.__cause__, httpx.HTTPStatusError):
            details = repr(e.__cause__.response.json()["code"])
        else:
            details = e.__cause__.__class__.__name__
        logging.exception(f"Error processing audio: {details}")
        return dict(text=f"❌ {e}", reply_markup=kb)

    await state.update_data(
        links={getattr(k, "name", k): v for k, v in links.items()},
        file_id=message.audio.file_id,
    )
    await state.set_state(SongPostStates.preparing)

    return message.reply_audio(
        message.audio.file_id,
        generate_audio_caption(links),
        parse_mode="HTML",
        reply_markup=POST_KB,
    )


@router.callback_query(
    admin_filter,
    SongPostStates.preparing,
    EditCallback.filter(F.what == "song"),
)
async def edit_song(query: CallbackQuery, state: FSMContext):
    # kb = InlineKeyboardMarkup(
    #     inline_keyboard=[
    #         [
    #             InlineKeyboardButton(
    #                 text="🌐 Download with youtube-dl",
    #                 callback_data=ActionCallback(action="ytdl").pack(),
    #             )
    #         ]  # TODO
    #     ]
    # )
    await query.message.edit_reply_markup()
    await state.set_state(SongPostStates.edit_song)
    m = await query.message.answer(
        "🎵 Send me new audio file",
        # reply_markup=kb,
    )
    await state.update_data(
        prompt_msg=m.message_id,
        reply_to=query.message.reply_to_message.message_id,
    )
    return query.answer()


@router.message(SongPostStates.edit_song, F.audio, flags={"chat_action": "upload_audio"})
async def save_audio(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    file_id = message.audio.file_id
    await state.update_data(file_id=file_id)
    await state.set_state(SongPostStates.preparing)
    caption = generate_audio_caption(data["links"])
    if data.get("suggested", False):
        caption += suggested_track_text((await bot.me()).username)
    return SendAudio(
        chat_id=message.chat.id,
        audio=file_id,
        caption=caption,
        parse_mode="HTML",
        reply_to_message_id=data["reply_to"],
        reply_markup=POST_KB,
    )


@router.callback_query(admin_filter, SongPostStates.preparing, EditCallback.filter())
async def edit_link(query: CallbackQuery, callback_data: EditCallback, state: FSMContext):
    key = callback_data.what
    service = Service(key)
    kb = InlineKeyboardBuilder().button(
        text="❌ Remove existing link",
        callback_data=ActionCallback(action=Action.POP_LINK),
    ).as_markup()
    await state.set_state(SongPostStates.edit)
    m = await query.message.answer(
        f"🔗 Enter new link for <i>{service.value}</i>",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await query.message.edit_reply_markup()
    await state.update_data(
        key=key.name,
        prompt_msg=m.message_id,
        reply_to=query.message.reply_to_message.message_id,
    )
    return query.answer()


@router.callback_query(
    admin_filter,
    SongPostStates.edit,
    ActionCallback.filter(F.action == Action.POP_LINK),
)
async def pop_link(query: CallbackQuery, bot: Bot, state: FSMContext):
    return await update_link(None, state, query.message.chat.id, bot)


@router.message(admin_filter, SongPostStates.edit, flags={"chat_action": "upload_audio"})
async def resend_with_edited(message: Message, bot: Bot, state: FSMContext):
    return await update_link(message.text, state, message.chat.id, bot)


async def update_link(
    new_value: str | None,
    state: FSMContext,
    chat_id: int,
    bot: Bot,
) -> SendAudio:
    data = await state.get_data()
    await bot.edit_message_reply_markup(chat_id, data["prompt_msg"])
    links = data["links"]
    if new_value is not None:
        links.update({data["key"]: new_value})
    else:
        try:
            links.pop(data["key"])
        except KeyError:
            pass  # it's ok if it's missing
    await state.update_data(links=links)
    await state.set_state(SongPostStates.preparing)
    caption = generate_audio_caption(links)
    if data.get("suggested", False):
        caption += suggested_track_text((await bot.me()).username)
    return SendAudio(
        chat_id=chat_id,
        audio=data["file_id"],
        caption=caption,
        parse_mode="HTML",
        reply_to_message_id=data["reply_to"],
        reply_markup=POST_KB,
    )


@router.callback_query(
    admin_filter,
    SongPostStates.preparing,
    ActionCallback.filter(F.action == Action.TOGGLE_SUGGESTED),
)
async def toggle_suggested(query: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    new_suggested = not data.get("suggested", False)
    await state.update_data(suggested=new_suggested)
    caption = generate_audio_caption(data["links"])
    if new_suggested:
        caption += suggested_track_text((await bot.me()).username)
    await query.message.edit_caption(caption, parse_mode="HTML", reply_markup=POST_KB)
    return query.answer()


@router.callback_query(admin_filter, SongPostStates.preparing, PostCallback.filter())
async def post(
    query: CallbackQuery,
    callback_data: PostCallback,
    state: FSMContext,
    config: Config,
):
    is_silent = not callback_data.notification
    dest = str(config.post_to)
    message = await query.message.copy_to(dest, disable_notification=is_silent)
    await state.clear()
    link_dest = dest.lstrip("@") if dest.startswith("@") else f"c/{dest.removeprefix('-100')}"
    await query.message.edit_caption(f"https://t.me/{link_dest}/{message.message_id}")
    return query.answer("📩{} Successfully posted!".format("🔕" if is_silent else "🔔"))


@router.callback_query(ActionCallback.filter(F.action == Action.CANCEL))
async def cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    if query.message.text:
        await query.message.edit_text("🚫 Post cancelled")
    else:
        await query.message.edit_reply_markup()
    return query.answer("👌")


@router.message(Command("start", "help"))
async def hello(event: Message):
    return event.reply(
        "👋 Hello! I can help you suggest new music to @evgenrandmuz! Simply send me"
        " the name of the track or the track itself and I'll forward it."
    )


@router.message(default_state, F.text | F.audio)
async def fwd(message: Message, config: Config):
    # TODO: throttle
    await message.copy_to(chat_id=config.admin)
    return message.reply("📩 Okay, I've forwarded it, thanks!")
