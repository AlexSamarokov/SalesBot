"""
FSM-flow создания рассылки.

Шаги:
1. Админ нажимает «Создать рассылку»
2. Вводит текст
3. Опционально прикрепляет медиа (фото / видео / документ)
4. Выбирает сегмент
5. Превью рассылки
6. Действия: отправить сейчас / запланировать / тест-отправка / сохранить черновик / отмена
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.middlewares.admin_check import AdminCheckMiddleware
from bot.db.database import get_db
from bot.db.queries import get_users_by_segment
from bot.handlers.admin.segments import (
    get_segment_keyboard,
    get_segment_filter,
    get_segment_label,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_broadcast")
router.message.middleware(AdminCheckMiddleware())
router.callback_query.middleware(AdminCheckMiddleware())


# ──────────────────────────────────────────────
# FSM States
# ──────────────────────────────────────────────

class BroadcastFSM(StatesGroup):
    waiting_text = State()
    waiting_media = State()
    waiting_segment = State()
    waiting_schedule_time = State()
    preview = State()


# ──────────────────────────────────────────────
# Шаг 1: Начало — ввод текста
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm:broadcast_new")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Начинает создание рассылки."""
    await callback.answer()
    await state.clear()

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✕ Отмена", callback_data="adm:broadcast_cancel")],
        ]
    )

    await callback.message.edit_text(
        text="<b>Создание рассылки</b>\n\nОтправьте текст рассылки:",
        reply_markup=cancel_kb,
    )
    await state.set_state(BroadcastFSM.waiting_text)


@router.message(BroadcastFSM.waiting_text)
async def receive_text(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получает текст рассылки."""
    if not message.text:
        await message.answer("Отправьте текст сообщения.")
        return

    await state.update_data(text=message.text)

    media_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Прикрепить медиа", callback_data="adm:broadcast_add_media")],
            [InlineKeyboardButton(text="Без медиа → выбор сегмента", callback_data="adm:broadcast_skip_media")],
            [InlineKeyboardButton(text="✕ Отмена", callback_data="adm:broadcast_cancel")],
        ]
    )

    await message.answer(
        text="Текст получен.\n\nХотите прикрепить медиа?",
        reply_markup=media_kb,
    )


# ──────────────────────────────────────────────
# Шаг 2: Медиа (опционально)
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm:broadcast_add_media")
async def ask_media(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Запрашивает медиа."""
    await callback.answer()

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без медиа → выбор сегмента", callback_data="adm:broadcast_skip_media")],
            [InlineKeyboardButton(text="✕ Отмена", callback_data="adm:broadcast_cancel")],
        ]
    )

    await callback.message.edit_text(
        text="Отправьте фото, видео или документ:",
        reply_markup=cancel_kb,
    )
    await state.set_state(BroadcastFSM.waiting_media)


@router.message(BroadcastFSM.waiting_media, F.photo)
async def receive_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получает фото для рассылки."""
    file_id = message.photo[-1].file_id
    await state.update_data(media_type="photo", media_file_id=file_id)
    await _go_to_segment_selection(message, state)


@router.message(BroadcastFSM.waiting_media, F.video)
async def receive_video(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получает видео для рассылки."""
    file_id = message.video.file_id
    await state.update_data(media_type="video", media_file_id=file_id)
    await _go_to_segment_selection(message, state)


@router.message(BroadcastFSM.waiting_media, F.document)
async def receive_document(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получает документ для рассылки."""
    file_id = message.document.file_id
    await state.update_data(media_type="document", media_file_id=file_id)
    await _go_to_segment_selection(message, state)


@router.message(BroadcastFSM.waiting_media)
async def receive_invalid_media(message: Message, state: FSMContext, bot: Bot) -> None:
    """Получает неподдерживаемое медиа."""
    await message.answer("Отправьте фото, видео или документ. Или нажмите «Без медиа».")


@router.callback_query(lambda c: c.data == "adm:broadcast_skip_media")
async def skip_media(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Пропуск медиа."""
    await callback.answer()
    await state.update_data(media_type=None, media_file_id=None)

    await callback.message.edit_text(
        text="<b>Выберите сегмент рассылки:</b>",
        reply_markup=get_segment_keyboard(page=0),
    )
    await state.set_state(BroadcastFSM.waiting_segment)


# ──────────────────────────────────────────────
# Шаг 3: Выбор сегмента
# ──────────────────────────────────────────────

async def _go_to_segment_selection(message: Message, state: FSMContext) -> None:
    """Переход к выбору сегмента."""
    await message.answer(
        text="<b>Выберите сегмент рассылки:</b>",
        reply_markup=get_segment_keyboard(page=0),
    )
    await state.set_state(BroadcastFSM.waiting_segment)


@router.callback_query(
    BroadcastFSM.waiting_segment,
    lambda c: c.data and c.data.startswith("adm:seg_page:"),
)
async def handle_segment_pagination(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Пагинация сегментов."""
    await callback.answer()
    page = int(callback.data.split(":")[-1])
    await callback.message.edit_reply_markup(reply_markup=get_segment_keyboard(page=page))


@router.callback_query(
    BroadcastFSM.waiting_segment,
    lambda c: c.data and c.data.startswith("adm:seg:"),
)
async def handle_segment_selected(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Сегмент выбран — показываем превью."""
    await callback.answer()

    segment_key = callback.data.split(":")[-1]
    segment_filter = get_segment_filter(segment_key)
    segment_label = get_segment_label(segment_key)

    if segment_filter is None:
        await callback.message.answer("Неизвестный сегмент.")
        return

    await state.update_data(
        segment_key=segment_key,
        segment_filter=segment_filter,
        segment_label=segment_label,
    )

    # Считаем получателей
    users = await get_users_by_segment(segment_filter)
    user_count = len(users)

    await state.update_data(user_count=user_count)
    await state.set_state(BroadcastFSM.preview)

    # Показываем превью
    await _show_preview(callback.message, state, user_count, segment_label)


# ──────────────────────────────────────────────
# Шаг 4: Превью
# ──────────────────────────────────────────────

async def _show_preview(
    message,
    state: FSMContext,
    user_count: int,
    segment_label: str,
) -> None:
    """Показывает превью рассылки."""
    data = await state.get_data()
    text = data.get("text", "")
    media_type = data.get("media_type")

    media_info = f"Медиа: {media_type}" if media_type else "Медиа: нет"

    preview_text = (
        f"<b>Превью рассылки</b>\n\n"
        f"<b>Сегмент:</b> {segment_label}\n"
        f"<b>Получателей:</b> {user_count}\n"
        f"<b>{media_info}</b>\n\n"
        f"<b>Текст:</b>\n{text[:500]}"
    )

    actions_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить сейчас", callback_data="adm:broadcast_send_now")],
            [InlineKeyboardButton(text="Запланировать", callback_data="adm:broadcast_schedule")],
            [InlineKeyboardButton(text="Тест-отправка (мне)", callback_data="adm:broadcast_test")],
            [InlineKeyboardButton(text="Сохранить черновик", callback_data="adm:broadcast_save_draft")],
            [InlineKeyboardButton(text="✕ Отмена", callback_data="adm:broadcast_cancel")],
        ]
    )

    await message.edit_text(text=preview_text, reply_markup=actions_kb)


# ──────────────────────────────────────────────
# Действия из превью
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm:broadcast_test")
async def handle_test_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Тест-отправка рассылки самому себе."""
    await callback.answer("Отправляю тест...")

    data = await state.get_data()
    admin_id = callback.from_user.id
    text = data.get("text", "")
    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")

    try:
        if media_type and media_file_id:
            if media_type == "photo":
                await bot.send_photo(chat_id=admin_id, photo=media_file_id, caption=text)
            elif media_type == "video":
                await bot.send_video(chat_id=admin_id, video=media_file_id, caption=text)
            elif media_type == "document":
                await bot.send_document(chat_id=admin_id, document=media_file_id, caption=text)
        else:
            await bot.send_message(chat_id=admin_id, text=text)

        await callback.message.answer("Тест-сообщение отправлено вам.")
    except Exception as e:
        await callback.message.answer(f"Ошибка тест-отправки: {e}")


@router.callback_query(lambda c: c.data == "adm:broadcast_send_now")
async def handle_send_now(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Немедленная отправка рассылки."""
    await callback.answer("Запускаю рассылку...")

    data = await state.get_data()
    broadcast_id = await _save_broadcast(data, callback.from_user.id, status="sending")

    # Отправляем
    segment_filter = data.get("segment_filter", {})
    users = await get_users_by_segment(segment_filter)

    text = data.get("text", "")
    media_type = data.get("media_type")
    media_file_id = data.get("media_file_id")
    now = datetime.now(timezone.utc).isoformat()

    sent = 0
    failed = 0

    for user in users:
        uid = user["telegram_id"]
        status = "sent"
        error = None

        try:
            if media_type and media_file_id:
                if media_type == "photo":
                    await bot.send_photo(chat_id=uid, photo=media_file_id, caption=text)
                elif media_type == "video":
                    await bot.send_video(chat_id=uid, video=media_file_id, caption=text)
                elif media_type == "document":
                    await bot.send_document(chat_id=uid, document=media_file_id, caption=text)
            else:
                await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception as e:
            error_msg = str(e).lower()
            if "forbidden" in error_msg or "blocked" in error_msg:
                status = "blocked"
                from bot.db.queries import update_user
                await update_user(uid, is_blocked=1)
            else:
                status = "failed"
            error = str(e)[:500]
            failed += 1

        # Лог
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO broadcast_logs (broadcast_id, user_id, status, error, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (broadcast_id, uid, status, error, now),
            )
            await db.commit()

    # Обновляем статус
    async with get_db() as db:
        await db.execute(
            "UPDATE broadcasts SET status = 'sent', sent_at = ? WHERE id = ?",
            (now, broadcast_id),
        )
        await db.commit()

    await state.clear()

    await callback.message.edit_text(
        text=(
            f"<b>Рассылка завершена</b>\n\n"
            f"Отправлено: {sent}\n"
            f"Ошибок: {failed}\n"
            f"Всего: {len(users)}"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
            ]
        ),
    )

    logger.info(
        "Broadcast %d sent by admin %d: %d/%d",
        broadcast_id, callback.from_user.id, sent, len(users),
    )


@router.callback_query(lambda c: c.data == "adm:broadcast_schedule")
async def handle_schedule(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Запрашивает время планирования."""
    await callback.answer()

    schedule_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Через 1 час", callback_data="adm:sched:1")],
            [InlineKeyboardButton(text="Через 3 часа", callback_data="adm:sched:3")],
            [InlineKeyboardButton(text="Через 6 часов", callback_data="adm:sched:6")],
            [InlineKeyboardButton(text="Через 12 часов", callback_data="adm:sched:12")],
            [InlineKeyboardButton(text="Через 24 часа", callback_data="adm:sched:24")],
            [InlineKeyboardButton(text="← Назад к превью", callback_data="adm:broadcast_back_preview")],
        ]
    )

    await callback.message.edit_text(
        text="<b>Когда отправить?</b>\n\nВыберите задержку:",
        reply_markup=schedule_kb,
    )
    await state.set_state(BroadcastFSM.waiting_schedule_time)


@router.callback_query(
    BroadcastFSM.waiting_schedule_time,
    lambda c: c.data and c.data.startswith("adm:sched:"),
)
async def handle_schedule_time(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Сохраняет рассылку с запланированным временем."""
    await callback.answer("Рассылка запланирована!")

    hours = int(callback.data.split(":")[-1])
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=hours)

    data = await state.get_data()
    broadcast_id = await _save_broadcast(
        data,
        callback.from_user.id,
        status="scheduled",
        scheduled_at=scheduled_at.isoformat(),
    )

    await state.clear()

    await callback.message.edit_text(
        text=(
            f"<b>Рассылка запланирована</b>\n\n"
            f"ID: {broadcast_id}\n"
            f"Сегмент: {data.get('segment_label', '—')}\n"
            f"Получателей: {data.get('user_count', '?')}\n"
            f"Отправка через: {hours} ч.\n"
            f"Время: {scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
            ]
        ),
    )

    logger.info(
        "Broadcast %d scheduled by admin %d for %s",
        broadcast_id, callback.from_user.id, scheduled_at.isoformat(),
    )


@router.callback_query(lambda c: c.data == "adm:broadcast_back_preview")
async def handle_back_to_preview(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Возврат к превью из планирования."""
    await callback.answer()
    data = await state.get_data()
    await state.set_state(BroadcastFSM.preview)
    await _show_preview(
        callback.message,
        state,
        data.get("user_count", 0),
        data.get("segment_label", ""),
    )


@router.callback_query(lambda c: c.data == "adm:broadcast_save_draft")
async def handle_save_draft(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Сохраняет рассылку как черновик."""
    await callback.answer("Черновик сохранён!")

    data = await state.get_data()
    broadcast_id = await _save_broadcast(data, callback.from_user.id, status="draft")

    await state.clear()

    await callback.message.edit_text(
        text=f"<b>Черновик сохранён</b>\n\nID: {broadcast_id}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
            ]
        ),
    )


@router.callback_query(lambda c: c.data == "adm:broadcast_cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Отмена создания рассылки."""
    await callback.answer("Отменено")
    await state.clear()

    await callback.message.edit_text(
        text="Создание рассылки отменено.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
            ]
        ),
    )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _save_broadcast(
    data: dict,
    admin_id: int,
    status: str = "draft",
    scheduled_at: str | None = None,
) -> int:
    """Сохраняет рассылку в БД и возвращает её id."""
    now = datetime.now(timezone.utc).isoformat()
    segment_filter = data.get("segment_filter", {})
    segment_json = json.dumps(segment_filter, ensure_ascii=False)

    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO broadcasts
                (created_by, text, media_type, media_file_id,
                 segment_filter, status, scheduled_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin_id,
                data.get("text", ""),
                data.get("media_type"),
                data.get("media_file_id"),
                segment_json,
                status,
                scheduled_at,
                now,
            ),
        )
        await db.commit()
        return cursor.lastrowid
