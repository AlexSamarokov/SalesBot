"""
Инициализация объектов aiogram: Bot и Dispatcher.
Импортируется из других модулей для доступа к bot и dp.
"""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import settings

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()
