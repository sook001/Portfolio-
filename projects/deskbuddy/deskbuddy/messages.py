"""ระบบบุคลิก: อ่านชุดข้อความจาก personalities/*.json แล้วสุ่มให้ไม่ซ้ำเดิม"""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

# ทุกบุคลิกต้องมีครบทุกหมวดนี้
REQUIRED_CONTEXTS = (
    "greeting_morning",
    "greeting_day",
    "greeting_evening",
    "greeting_night",
    "greeting_back",
    "break",
    "break_again",
    "death_streak",
    "meal_breakfast",
    "meal_lunch",
    "meal_dinner",
    "late_night",
    "reply_ate",
    "reply_not_yet",
    "reply_snooze",
    "reply_rest",
    "reply_continue",
    "reply_sleep",
    "reply_sleep_later",
)


class _SafeDict(dict):
    def __missing__(self, key):  # ตัวแปรที่ไม่รู้จักให้คงไว้ ไม่ให้ error
        return "{" + key + "}"


class Personality:
    def __init__(self, data: dict, user_name: str = "", rng: random.Random | None = None):
        messages = data.get("messages")
        if not isinstance(messages, dict):
            raise ValueError("ไฟล์บุคลิกต้องมีคีย์ 'messages'")
        missing = [c for c in REQUIRED_CONTEXTS if not messages.get(c)]
        if missing:
            raise ValueError("ไฟล์บุคลิกขาดหมวดข้อความ: " + ", ".join(missing))
        self.name = data.get("name", "")
        self.messages = messages
        self.user_name = (user_name or "").strip()
        self.rng = rng or random.Random()
        self._last: dict[str, str] = {}

    @classmethod
    def load(cls, path: Path, user_name: str = "", rng: random.Random | None = None):
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f), user_name, rng)

    def pick(self, context: str, **variables) -> str:
        options = list(self.messages.get(context, []))
        if not self.user_name:
            # ไม่มีชื่อ: ข้ามข้อความที่ต้องเรียกชื่อ
            options = [o for o in options if "{name}" not in o]
        if not options:
            return ""
        last = self._last.get(context)
        if len(options) > 1 and last in options:
            options.remove(last)
        choice = self.rng.choice(options)
        self._last[context] = choice
        variables.setdefault("name", self.user_name)
        return string.Formatter().vformat(choice, (), _SafeDict(variables))
