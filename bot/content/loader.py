"""
Загрузчик контента из YAML-файлов.

Читает все YAML-файлы из директории content/, индексирует экраны по их id
для O(1)-доступа. Также предоставляет доступ к мета-данным веток,
nurture-конфигу и глобальному меню.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from bot.config import settings

logger = logging.getLogger(__name__)


class ContentManager:
    """Загружает и хранит весь контент бота из YAML."""

    def __init__(self) -> None:
        # Индекс: screen_id → screen dict
        self.screens: Dict[str, Dict[str, Any]] = {}

        # Мета-данные веток: branch_id → branch dict (содержит manager_messages, nurture и т.д.)
        self.branches: Dict[str, Dict[str, Any]] = {}

        # Глобальное меню
        self.global_menu: Dict[str, Any] = {}

        # Мета-настройки nurture
        self.nurture_meta: Dict[str, Any] = {}

        # Routing rules из shared_role_select_3
        self.routing_rules: List[Dict[str, str]] = []

    def load_all(self) -> None:
        """Загружает все YAML-файлы и строит индексы."""
        content_dir = Path(settings.CONTENT_DIR)

        self._load_shared_screens(content_dir / "shared_screens.yaml")
        self._load_branches(content_dir / "parent_branches.yaml")
        self._load_branches(content_dir / "student_branches.yaml")
        self._load_global_menu(content_dir / "global_menu.yaml")
        self._load_nurture_meta(content_dir / "nurture_meta.yaml")

        logger.info(
            "Контент загружен: %d экранов, %d веток",
            len(self.screens),
            len(self.branches),
        )

    # ──────────────────────────────────────────────
    # Публичные методы доступа
    # ──────────────────────────────────────────────

    def get_screen(self, screen_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает конфиг экрана по его id или None."""
        return self.screens.get(screen_id)

    def get_branch(self, branch_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает мета-данные ветки по её id или None."""
        return self.branches.get(branch_id)

    def get_branch_final_screen_id(self, branch_id: str) -> Optional[str]:
        """Возвращает id финального CTA-экрана ветки (экран _10)."""
        branch = self.branches.get(branch_id)
        if not branch:
            return None
        screens = branch.get("screen_ids", [])
        if not screens:
            return None
        return screens[-1]

    def get_nurture_screen_id(self, branch_id: str, step: int) -> Optional[str]:
        """Возвращает screen_id для nurture-шага ветки.

        step начинается с 1.
        """
        branch = self.branches.get(branch_id)
        if not branch:
            return None
        nurture_ids = branch.get("nurture_screen_ids", [])
        if step < 1 or step > len(nurture_ids):
            return None
        return nurture_ids[step - 1]

    def get_nurture_total_steps(self, branch_id: str) -> int:
        """Возвращает количество шагов nurture для ветки."""
        branch = self.branches.get(branch_id)
        if not branch:
            return 0
        return len(branch.get("nurture_screen_ids", []))

    def get_manager_message(self, branch_id: str, message_key: str) -> str:
        """Возвращает заготовленный текст для менеджера."""
        branch = self.branches.get(branch_id)
        if not branch:
            return ""
        messages = branch.get("manager_messages", {})
        return messages.get(message_key, "")

    def get_nurture_delay_hours(self, step: int) -> int:
        """Возвращает задержку в часах перед отправкой nurture-шага."""
        schedule = self.nurture_meta.get("schedule", {})
        key = f"nurture_step_{step}_delay_hours"
        return schedule.get(key, 24)

    # ──────────────────────────────────────────────
    # Приватные методы загрузки
    # ──────────────────────────────────────────────

    def _load_yaml(self, path: Path) -> Any:
        """Читает YAML-файл."""
        if not path.exists():
            logger.warning("YAML-файл не найден: %s", path)
            return None
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _index_screen(self, screen_data: Dict[str, Any]) -> None:
        """Добавляет экран в индекс."""
        # screen_data может быть обёрнут в ключ "screen" или быть плоским
        if "screen" in screen_data and isinstance(screen_data["screen"], dict):
            screen = screen_data["screen"]
        else:
            screen = screen_data

        screen_id = screen.get("id")
        if not screen_id:
            logger.warning("Экран без id: %s", screen)
            return

        self.screens[screen_id] = screen

        # Сохраняем routing_rules если есть
        transitions = screen.get("transitions", {})
        if transitions.get("dynamic_routing") and "routing_rules" in transitions:
            self.routing_rules = transitions["routing_rules"]

    def _load_shared_screens(self, path: Path) -> None:
        """Загружает общие экраны."""
        data = self._load_yaml(path)
        if not data or "screens" not in data:
            return

        for screen_entry in data["screens"]:
            self._index_screen(screen_entry)

    def _load_branches(self, path: Path) -> None:
        """Загружает ветки (parent или student) и индексирует все экраны."""
        data = self._load_yaml(path)
        if not data or "branches" not in data:
            return

        for branch_entry in data["branches"]:
            # branch_entry может быть обёрнут в ключ "branch"
            if "branch" in branch_entry and isinstance(branch_entry["branch"], dict):
                branch = branch_entry["branch"]
            else:
                branch = branch_entry

            branch_id = branch.get("id")
            if not branch_id:
                continue

            # Собираем id экранов ветки
            screen_ids: List[str] = []
            for screen_entry in branch.get("screens", []):
                self._index_screen(screen_entry)
                s = screen_entry.get("screen", screen_entry)
                if s.get("id"):
                    screen_ids.append(s["id"])

            # Собираем nurture-экраны
            nurture_screen_ids: List[str] = []
            nurture_data = branch.get("nurture", {})
            nurture_manager_messages: Dict[str, str] = {}

            if nurture_data:
                for screen_entry in nurture_data.get("sequence", []):
                    self._index_screen(screen_entry)
                    s = screen_entry.get("screen", screen_entry)
                    if s.get("id"):
                        nurture_screen_ids.append(s["id"])

                nurture_manager_messages = nurture_data.get("manager_messages", {})

            # Собираем manager_messages ветки
            branch_manager_messages = branch.get("manager_messages", {})
            # Объединяем с nurture manager_messages
            all_manager_messages = {**branch_manager_messages, **nurture_manager_messages}

            self.branches[branch_id] = {
                "id": branch_id,
                "role": branch.get("role"),
                "goal": branch.get("goal"),
                "title": branch.get("title"),
                "screen_ids": screen_ids,
                "nurture_screen_ids": nurture_screen_ids,
                "manager_messages": all_manager_messages,
            }

    def _load_global_menu(self, path: Path) -> None:
        """Загружает конфигурацию глобального меню."""
        data = self._load_yaml(path)
        if data and "global_menu" in data:
            self.global_menu = data["global_menu"]

    def _load_nurture_meta(self, path: Path) -> None:
        """Загружает мета-настройки nurture."""
        data = self._load_yaml(path)
        if data and "nurture_meta" in data:
            self.nurture_meta = data["nurture_meta"]


# Глобальный синглтон
content_manager = ContentManager()
