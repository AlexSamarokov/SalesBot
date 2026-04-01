"""
Сервис динамического роутинга.

По связке (goal, role) определяет, на какой экран ветки
перенаправить пользователя после экрана выбора роли (shared_role_select_3).
Также определяет branch_id для записи в состояние пользователя.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from bot.content.loader import content_manager

logger = logging.getLogger(__name__)

# Маппинг (goal, role) → (screen_id, branch_id)
# Строится из routing_rules загруженных из shared_role_select_3
# Если routing_rules не загружены, используем хардкоженный fallback

_FALLBACK_ROUTES = {
    ("goal_school_math", "role_parent"): ("parent_schoolmath_4", "parent_school_math"),
    ("goal_exam", "role_parent"): ("parent_exam_4", "parent_exam"),
    ("goal_olymp", "role_parent"): ("parent_olymp_4", "parent_olymp"),
    ("goal_unsure", "role_parent"): ("parent_unsure_4", "parent_unsure"),
    ("goal_school_math", "role_student"): ("student_schoolmath_4", "student_school_math"),
    ("goal_exam", "role_student"): ("student_exam_4", "student_exam"),
    ("goal_olymp", "role_student"): ("student_olymp_4", "student_olymp"),
    ("goal_unsure", "role_student"): ("student_unsure_4", "student_unsure"),
}


def resolve_route(goal: str, role: str) -> Optional[Tuple[str, str]]:
    """Определяет целевой экран и ветку по goal и role.

    Возвращает (screen_id, branch_id) или None если маршрут не найден.
    """
    # Сначала пробуем routing_rules из YAML
    for rule in content_manager.routing_rules:
        if rule.get("if_goal") == goal and rule.get("if_role") == role:
            screen_id = rule.get("go_to", "")
            if screen_id:
                # Определяем branch_id из экрана
                branch_id = _infer_branch_id(screen_id, goal, role)
                logger.info(
                    "Route resolved (YAML): goal=%s, role=%s → screen=%s, branch=%s",
                    goal, role, screen_id, branch_id,
                )
                return screen_id, branch_id

    # Fallback на хардкоженную таблицу
    key = (goal, role)
    if key in _FALLBACK_ROUTES:
        screen_id, branch_id = _FALLBACK_ROUTES[key]
        logger.info(
            "Route resolved (fallback): goal=%s, role=%s → screen=%s, branch=%s",
            goal, role, screen_id, branch_id,
        )
        return screen_id, branch_id

    logger.error("Route not found: goal=%s, role=%s", goal, role)
    return None


def _infer_branch_id(screen_id: str, goal: str, role: str) -> str:
    """Определяет branch_id по screen_id или по goal+role.

    Ищет в загруженных ветках, какая из них содержит данный screen_id.
    Если не нашёл — строит branch_id из goal и role.
    """
    for branch_id, branch_data in content_manager.branches.items():
        if screen_id in branch_data.get("screen_ids", []):
            return branch_id

    # Fallback: строим из goal+role
    key = (goal, role)
    if key in _FALLBACK_ROUTES:
        return _FALLBACK_ROUTES[key][1]

    # Последний fallback
    role_prefix = "parent" if role == "role_parent" else "student"
    goal_suffix = goal.replace("goal_", "")
    return f"{role_prefix}_{goal_suffix}"
