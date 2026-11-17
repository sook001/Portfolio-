"""ตรรกะของหน้าตั้งค่า (ไม่ใช้ tkinter จึงทดสอบได้ทุกเครื่อง)"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

MEAL_LABELS = {"breakfast": "มื้อเช้า", "lunch": "มื้อเที่ยง", "dinner": "มื้อเย็น"}

# ปุ่มในแท็บ "ทดสอบ": (หัวข้อ, [(รหัสตัวอย่างของ Engine.preview, ข้อความบนปุ่ม), ...])
PREVIEW_GROUPS = (
    (
        "ทักทายตอนเปิดเครื่อง",
        [
            ("greeting_morning", "ตอนเช้า"),
            ("greeting_day", "ตอนกลางวัน"),
            ("greeting_evening", "ตอนเย็น"),
            ("greeting_night", "ตอนดึก"),
            ("greeting_back", "กลับมาหลังหายไปหลายวัน"),
        ],
    ),
    (
        "ถามเรื่องกินข้าว",
        [("meal_breakfast", "มื้อเช้า"), ("meal_lunch", "มื้อเที่ยง"), ("meal_dinner", "มื้อเย็น")],
    ),
    (
        "ตอนเล่นเกม",
        [("break", "ถามพัก (เล่นนาน)"), ("break_again", "ถามพักรอบที่สอง"), ("death", "ตายซ้ำ ๆ")],
    ),
    ("ตอนดึก", [("night", "ทักเรื่องนอน")]),
)

_TIME_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


def parse_time(text: str) -> str:
    """รับ '7:30' หรือ '07.30' คืน '07:30' ถ้ารูปแบบผิดจะ raise ValueError"""
    match = _TIME_RE.match(text or "")
    if not match:
        raise ValueError("เวลาต้องเป็นรูปแบบ ชั่วโมง:นาที เช่น 12:30")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError("เวลาต้องอยู่ระหว่าง 00:00 ถึง 23:59")
    return f"{hours:02d}:{minutes:02d}"


def parse_time_range(label: str, start: str, end: str) -> tuple:
    try:
        s, e = parse_time(start), parse_time(end)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from None
    if s == e:
        raise ValueError(f"{label}: เวลาเริ่มกับเวลาจบต้องไม่เท่ากัน")
    return s, e


def parse_processes(text: str) -> list:
    """แยกชื่อ process ที่คั่นด้วยจุลภาค/ขึ้นบรรทัดใหม่ เติม .exe ให้ถ้าลืมใส่ และตัดตัวซ้ำ"""
    names: list = []
    seen = set()
    for part in re.split(r"[,\n;]", text or ""):
        name = part.strip().strip('"')
        if not name:
            continue
        if not name.lower().endswith(".exe"):
            name += ".exe"
        if name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def validate_game_fields(name: str, processes_text: str, window_text: str, other_names) -> tuple:
    name = (name or "").strip()
    if not name:
        raise ValueError("ใส่ชื่อเกมด้วย")
    if name.lower() in {n.lower() for n in other_names}:
        raise ValueError(f"มีเกมชื่อ '{name}' อยู่แล้ว")
    processes = parse_processes(processes_text)
    if not processes:
        raise ValueError("ใส่ชื่อ process (.exe) อย่างน้อย 1 ตัว\nดูได้จาก Task Manager แท็บ Details หรือกดปุ่ม 'เลือกจากโปรแกรมที่กำลังรัน'")
    window = (window_text or "").strip() or None
    return name, processes, window


def build_config(cfg: dict, *, user_name: str, personality: str, meals: dict, night: tuple) -> dict:
    """สร้าง config ใหม่จากค่าในฟอร์ม โดยไม่แตะค่าอื่นที่หน้าตั้งค่าไม่ได้ให้แก้

    meals: {"breakfast": (เปิดไหม, "07:00", "09:30"), ...}
    night: (เปิดไหม, "01:00", "05:00")
    """
    if not personality:
        raise ValueError("ยังไม่ได้เลือกบุคลิก")
    new = copy.deepcopy(cfg)
    new["user_name"] = (user_name or "").strip()
    new["personality"] = personality
    new.setdefault("meals", {})
    new.setdefault("meals_enabled", {})
    for key, (enabled, start, end) in meals.items():
        s, e = parse_time_range(MEAL_LABELS.get(key, key), start, end)
        new["meals"][key] = [s, e]
        new["meals_enabled"][key] = bool(enabled)
    enabled, start, end = night
    s, e = parse_time_range("ช่วงเวลาทักเรื่องนอน", start, end)
    late = new.setdefault("late_night", {})
    late["enabled"] = bool(enabled)
    late["start"], late["end"] = s, e
    return new


def list_personalities(directory: Path) -> list:
    """คืน [(ชื่อไฟล์ไม่มี .json, ชื่อที่แสดง), ...] เฉพาะไฟล์ที่อ่านได้"""
    out = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("messages"), dict):
            out.append((path.stem, str(data.get("name") or path.stem)))
    return out
