"""
Управление черновиками рассылок.

Показывает список черновиков, позволяет загрузить,
отправить, запланировать или удалить черновик.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.middlewares.admin_check import AdminCheckMiddleware
from bot.db.database import get_db
from bot.db.queries import get_users_by_segment
from bot.handlers.admin.segments import get_segment_label

logger = logging.getLogger(__name__)

router = Router(name="admin_drafts")
router.message.middleware(AdminCheckMiddleware())
router.callback_query.middleware(AdminCheckMiddleware())


# ──────────────────────────────────────────────
# Список черновиков
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "adm:drafts_list")
async def handle_drafts_list(callback: CallbackQuery, bot: Bot) -> None:
    """Показывает список черновиков и запланированных рассылок."""
    await callback.answer()

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, text, media_type, segment_filter, status, scheduled_at, created_at
            FROM broadcasts
            WHERE status IN ('draft', 'scheduled')
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )
        rows = await cursor.fetchall()
        drafts = [dict(r) for r in rows]

    if not drafts:
        await callback.message.edit_text(
            text="Черновиков и запланированных рассылок нет.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
                ]
            ),
        )
        return

    rows_kb: list[list[InlineKeyboardButton]] = []
    for draft in drafts:
        draft_id = draft["id"]
        status_icon = "📝" if draft["status"] == "draft" else "⏰"
        text_preview = draft["text"][:40].replace("\n", " ")
        label = f"{status_icon} #{draft_id}: {text_preview}..."

        rows_kb.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"adm:draft_view:{draft_id}",
            )
        ])

    rows_kb.append([
        InlineKeyboardButton(text="← В меню", callback_data="adm:menu"),
    ])

    await callback.message.edit_text(
        text="<b>Черновики и запланированные рассылки</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows_kb),
    )


# ──────────────────────────────────────────────
# Просмотр одного черновика
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_view:"))
async def handle_draft_view(callback: CallbackQuery, bot: Bot) -> None:
    """Показывает детали черновика."""
    await callback.answer()

    draft_id = int(callback.data.split(":")[-1])

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM broadcasts WHERE id = ?",
            (draft_id,),
        )
        row = await cursor.fetchone()

    if not row:
        await callback.message.edit_text(
            text="Черновик не найден.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="← Назад", callback_data="adm:drafts_list")],
                ]
            ),
        )
        return

    draft = dict(row)
    media_info = f"Медиа: {draft['media_type']}" if draft.get("media_type") else "Медиа: нет"

    # Определяем сегмент
    seg_filter = {}
    try:
        seg_filter = json.loads(draft.get("segment_filter", "{}") or "{}")
    except json.JSONDecodeError:
        pass

    seg_label = _filter_to_label(seg_filter)

    schedule_info = ""
    if draft["status"] == "scheduled" and draft.get("scheduled_at"):
        schedule_info = f"\nЗапланирована на: {draft['scheduled_at'][:16]} UTC"

    text = (
        f"<b>Рассылка #{draft['id']}</b>\n"
        f"Статус: {draft['status']}{schedule_info}\n"
        f"Сегмент: {seg_label}\n"
        f"{media_info}\n"
        f"Создана: {draft['created_at'][:16]}\n\n"
        f"<b>Текст:</b>\n{draft['text'][:500]}"
    )

    actions: list[list[InlineKeyboardButton]] = []

    if draft["status"] == "draft":
        actions.append([
            InlineKeyboardButton(
                text="Отправить сейчас",
                callback_data=f"adm:draft_send:{draft_id}",
            ),
        ])
        actions.append([
            InlineKeyboardButton(
                text="Запланировать (через 1 ч)",
                callback_data=f"adm:draft_sched:{draft_id}",
            ),
        ])

    if draft["status"] == "scheduled":
        actions.append([
            InlineKeyboardButton(
                text="Отменить планирование",
                callback_data=f"adm:draft_unsched:{draft_id}",
            ),
        ])

    actions.append([
        InlineKeyboardButton(
            text="Тест-отправка (мне)",
            callback_data=f"adm:draft_test:{draft_id}",
        ),
    ])
    actions.append([
        InlineKeyboardButton(
            text="Удалить",
            callback_data=f"adm:draft_delete:{draft_id}",
        ),
    ])
    actions.append([
        InlineKeyboardButton(text="← Назад", callback_data="adm:drafts_list"),
    ])

    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=actions),
    )


# ──────────────────────────────────────────────
# Действия с черновиком
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_test:"))
async def handle_draft_test(callback: CallbackQuery, bot: Bot) -> None:
    """Тест-отправка черновика."""
    await callback.answer("Отправляю тест...")

    draft_id = int(callback.data.split(":")[-1])
    draft = await _get_broadcast(draft_id)
    if not draft:
        return

    admin_id = callback.from_user.id

    try:
        await _send_to_user(bot, admin_id, draft)
        await callback.message.answer("Тест-сообщение отправлено.")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_send:"))
async def handle_draft_send(callback: CallbackQuery, bot: Bot) -> None:
    """Немедленная отправка черновика."""
    await callback.answer("Запускаю рассылку...")

    draft_id = int(callback.data.split(":")[-1])
    draft = await _get_broadcast(draft_id)
    if not draft:
        await callback.message.answer("Черновик не найден.")
        return

    # Получаем сегмент
    seg_filter = {}
    try:
        seg_filter = json.loads(draft.get("segment_filter", "{}") or "{}")
    except json.JSONDecodeError:
        pass

    users = await get_users_by_segment(seg_filter)
    now = datetime.now(timezone.utc).isoformat()

    sent = 0
    failed = 0

    async with get_db() as db:
        await db.execute(
            "UPDATE broadcasts SET status = 'sending' WHERE id = ?",
            (draft_id,),
        )
        await db.commit()

    for user in users:
        uid = user["telegram_id"]
        status = "sent"
        error = None

        try:
            await _send_to_user(bot, uid, draft)
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

        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO broadcast_logs (broadcast_id, user_id, status, error, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (draft_id, uid, status, error, now),
            )
            await db.commit()

    async with get_db() as db:
        await db.execute(
            "UPDATE broadcasts SET status = 'sent', sent_at = ? WHERE id = ?",
            (now, draft_id),
        )
        await db.commit()

    await callback.message.edit_text(
        text=(
            f"<b>Рассылка #{draft_id} завершена</b>\n\n"
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


@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_sched:"))
async def handle_draft_schedule(callback: CallbackQuery, bot: Bot) -> None:
    """Планирует черновик на 1 час вперёд."""
    await callback.answer("Запланировано!")

    draft_id = int(callback.data.split(":")[-1])
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)

    async with get_db() as db:
        await db.execute(
            "UPDATE broadcasts SET status = 'scheduled', scheduled_at = ? WHERE id = ?",
            (scheduled_at.isoformat(), draft_id),
        )
        await db.commit()

    await callback.message.edit_text(
        text=(
            f"<b>Рассылка #{draft_id} запланирована</b>\n\n"
            f"Отправка: {scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← В меню", callback_data="adm:menu")],
            ]
        ),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_unsched:"))
async def handle_draft_unschedule(callback: CallbackQuery, bot: Bot) -> None:
    """Отменяет планирование — возвращает в черновики."""
    await callback.answer("Планирование отменено")

    draft_id = int(callback.data.split(":")[-1])

    async with get_db() as db:
        await db.execute(
            "UPDATE broadcasts SET status = 'draft', scheduled_at = NULL WHERE id = ?",
            (draft_id,),
        )
        await db.commit()

    await callback.message.edit_text(
        text=f"Рассылка #{draft_id} возвращена в черновики.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← К черновикам", callback_data="adm:drafts_list")],
            ]
        ),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("adm:draft_delete:"))
async def handle_draft_delete(callback: CallbackQuery, bot: Bot) -> None:
    """Удаляет черновик."""
    await callback.answer("Удалено")

    draft_id = int(callback.data.split(":")[-1])

    async with get_db() as db:
        await db.execute("DELETE FROM broadcast_logs WHERE broadcast_id = ?", (draft_id,))
        await db.execute("DELETE FROM broadcasts WHERE id = ?", (draft_id,))
        await db.commit()

    await callback.message.edit_text(
        text=f"Рассылка #{draft_id} удалена.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← К черновикам", callback_data="adm:drafts_list")],
            ]
        ),
    )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _get_broadcast(broadcast_id: int) -> dict | None:
    """Получает рассылку из БД."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM broadcasts WHERE id = ?",
            (broadcast_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _send_to_user(bot: Bot, user_id: int, draft: dict) -> None:
    """Отправляет рассылку одному пользователю."""
    text = draft["text"]
    media_type = draft.get("media_type")
    media_file_id = draft.get("media_file_id")

    if media_type and media_file_id:
        if media_type == "photo":
            await bot.send_photo(chat_id=user_id, photo=media_file_id, caption=text)
        elif media_type == "video":
            await bot.send_video(chat_id=user_id, video=media_file_id, caption=text)
        elif media_type == "document":
            await bot.send_document(chat_id=user_id, document=media_file_id, caption=text)
        else:
            await bot.send_message(chat_id=user_id, text=text)
    else:
        await bot.send_message(chat_id=user_id, text=text)


def _filter_to_label(seg_filter: dict) -> str:
    """Преобразует фильтр сегмента в читаемый текст."""
    if not seg_filter:
        return "Все пользователи"

    parts = []
    for k, v in seg_filter.items():
        parts.append(f"{k}={v}")
    return ", ".join(parts)
