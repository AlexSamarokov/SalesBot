"""
Главное меню администратора.

/admin — показывает панель с кнопками:
- Создать рассылку
- Черновики
- Статистика
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.middlewares.admin_check import AdminCheckMiddleware
from bot.db.database import get_db

logger = logging.getLogger(__name__)

router = Router(name="admin_menu")
router.message.middleware(AdminCheckMiddleware())
router.callback_query.middleware(AdminCheckMiddleware())


def _admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного админ-меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать рассылку", callback_data="adm:broadcast_new")],
            [InlineKeyboardButton(text="Черновики", callback_data="adm:drafts_list")],
            [InlineKeyboardButton(text="Статистика", callback_data="adm:stats")],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, bot: Bot) -> None:
    """Показывает главное меню администратора."""
    await message.answer(
        text="<b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=_admin_menu_keyboard(),
    )
    logger.info("Admin menu opened by user %d", message.from_user.id)


@router.callback_query(lambda c: c.data == "adm:menu")
async def handle_back_to_menu(callback: CallbackQuery, bot: Bot) -> None:
    """Возврат в главное меню админа."""
    await callback.answer()
    await callback.message.edit_text(
        text="<b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=_admin_menu_keyboard(),
    )


@router.callback_query(lambda c: c.data == "adm:stats")
async def handle_stats(callback: CallbackQuery, bot: Bot) -> None:
    """Показывает базовую статистику."""
    await callback.answer()

    async with get_db() as db:
        # Общее количество пользователей
        cur = await db.execute("SELECT COUNT(*) as cnt FROM users")
        total = (await cur.fetchone())["cnt"]

        # Активные (не заблокировавшие)
        cur = await db.execute("SELECT COUNT(*) as cnt FROM users WHERE is_blocked = 0")
        active = (await cur.fetchone())["cnt"]

        # По ролям
        cur = await db.execute(
            "SELECT role, COUNT(*) as cnt FROM users WHERE role IS NOT NULL GROUP BY role"
        )
        roles = {row["role"]: row["cnt"] for row in await cur.fetchall()}

        # По целям
        cur = await db.execute(
            "SELECT goal, COUNT(*) as cnt FROM users WHERE goal IS NOT NULL GROUP BY goal"
        )
        goals = {row["goal"]: row["cnt"] for row in await cur.fetchall()}

        # Кликнули CTA
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE clicked_trial_cta = 1 OR clicked_manager_cta = 1"
        )
        cta_clicked = (await cur.fetchone())["cnt"]

        # В nurture
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM nurture_queue WHERE is_active = 1"
        )
        in_nurture = (await cur.fetchone())["cnt"]

        # Рассылки
        cur = await db.execute("SELECT COUNT(*) as cnt FROM broadcasts")
        broadcasts_total = (await cur.fetchone())["cnt"]

    # Форматируем роли
    role_lines = "\n".join(
        f"  {_role_label(k)}: {v}" for k, v in sorted(roles.items())
    ) or "  Нет данных"

    goal_lines = "\n".join(
        f"  {_goal_label(k)}: {v}" for k, v in sorted(goals.items())
    ) or "  Нет данных"

    text = (
        f"<b>Статистика</b>\n\n"
        f"Всего пользователей: {total}\n"
        f"Активных: {active}\n"
        f"Кликнули CTA: {cta_clicked}\n"
        f"В nurture-очереди: {in_nurture}\n"
        f"Рассылок создано: {broadcasts_total}\n\n"
        f"<b>По ролям:</b>\n{role_lines}\n\n"
        f"<b>По целям:</b>\n{goal_lines}"
    )

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="adm:menu")],
        ]
    )

    await callback.message.edit_text(text=text, reply_markup=back_kb)


def _role_label(role: str) -> str:
    labels = {
        "role_parent": "Родители",
        "role_student": "Школьники",
    }
    return labels.get(role, role)


def _goal_label(goal: str) -> str:
    labels = {
        "goal_school_math": "Школьная математика",
        "goal_exam": "ОГЭ / ЕГЭ",
        "goal_olymp": "Олимпиады / поступление",
        "goal_unsure": "Не определились",
    }
    return labels.get(goal, goal)
