import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
from uuid import uuid4

TODOS_DIR = os.environ.get("TODOS_DIR", os.path.join(os.getcwd(), "todos"))
MAX_TODOS = 100


class TodoItem:
    def __init__(
        self,
        text: str,
        datetime_str: str = "",
        completed: bool = False,
        todo_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ):
        self.id = todo_id or f"todo_{uuid4().hex[:12]}"
        self.text = text
        self.datetime = datetime_str
        self.completed = completed
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "datetime": self.datetime,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoItem":
        return cls(
            text=data["text"],
            datetime_str=data.get("datetime", ""),
            completed=data.get("completed", False),
            todo_id=data.get("id"),
            created_at=data.get("created_at"),
        )


class TodoManager:
    def __init__(self, base_dir: str = TODOS_DIR):
        self._base_dir = base_dir
        self._cache: List[TodoItem] | None = None

    def _file_path(self) -> str:
        return os.path.join(self._base_dir, "todos.json")

    def load(self) -> List[TodoItem]:
        file_path = self._file_path()
        if not os.path.exists(file_path):
            self._cache = []
            return []
        try:
            with open(file_path) as f:
                data = json.load(f)
            self._cache = [TodoItem.from_dict(item) for item in data]
            return self._cache
        except Exception as e:
            logger.error(f"Failed to load todos: {e}")
            self._cache = []
            return []

    def save(self, items: List[TodoItem]) -> None:
        os.makedirs(self._base_dir, exist_ok=True)
        data = [item.to_dict() for item in items]
        try:
            with open(self._file_path(), "w") as f:
                json.dump(data, f, indent=2)
            self._cache = items
        except Exception as e:
            logger.error(f"Failed to save todos: {e}")

    def add(self, text: str, datetime_str: str = "") -> TodoItem:
        if datetime_str:
            try:
                datetime.fromisoformat(datetime_str)
            except ValueError:
                datetime_str = ""
        item = TodoItem(text=text, datetime_str=datetime_str)
        items = self.load()
        items.append(item)
        if len(items) > MAX_TODOS:
            items = items[-MAX_TODOS:]
        self.save(items)
        return item

    def delete(self, todo_id: str) -> bool:
        items = self.load()
        filtered = [i for i in items if i.id != todo_id]
        if len(filtered) == len(items):
            return False
        self.save(filtered)
        return True

    def update(
        self,
        todo_id: str,
        text: Optional[str] = None,
        datetime_str: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> Optional[TodoItem]:
        items = self.load()
        for item in items:
            if item.id == todo_id:
                if text is not None:
                    item.text = text
                if datetime_str is not None:
                    item.datetime = datetime_str
                if completed is not None:
                    item.completed = completed
                self.save(items)
                return item
        return None

    def get_due_todos(self) -> List[TodoItem]:
        items = self.load()
        now = datetime.now(timezone.utc)
        due = []
        for item in items:
            if item.completed or not item.datetime:
                continue
            try:
                dt = datetime.fromisoformat(item.datetime)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt <= now:
                    due.append(item)
            except (ValueError, TypeError):
                continue
        return due

    def to_prompt_string(self) -> str:
        items = self.load()
        pending = [i for i in items if not i.completed]
        lines = []
        for item in pending:
            parts = [f"- {item.text}"]
            if item.datetime:
                try:
                    dt = datetime.fromisoformat(item.datetime)
                    parts.append(f"(at {dt.strftime('%Y-%m-%d %H:%M')})")
                except (ValueError, TypeError):
                    parts.append(f"(at {item.datetime})")
            lines.append(" ".join(parts))
        if not lines:
            return ""
        prompt = "[TODO LIST]\n"
        prompt += "\n".join(lines)
        prompt += "\n\nWhen you receive '⏰ Reminder: ...' as input, it means a reminder time has arrived. Acknowledge it naturally and remind the user."
        return prompt
