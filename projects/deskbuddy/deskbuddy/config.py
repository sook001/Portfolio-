"""โหลด/บันทึกการตั้งค่า (config.json) โดยเติมค่าเริ่มต้นให้อัตโนมัติ"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

DEFAULTS = {
    # ชื่อที่ให้เพื่อนเรียก (เว้นว่างได้ ข้อความที่ใช้ {name} จะไม่ถูกสุ่มมาใช้)
    "user_name": "",
    # ชื่อไฟล์ในโฟลเดอร์ personalities/ (ไม่ต้องใส่ .json)
    "personality": "friendly",
    # ตรวจ process ทุกกี่วินาที
    "scan_interval_seconds": 5,
    # รอกี่วินาทีหลังเปิดโปรแกรมก่อนทักทายครั้งแรก
    "startup_greeting_delay_seconds": 15,
    # เล่นต่อเนื่องกี่นาทีถึงจะถามว่าพักไหม
    "break_after_minutes": 120,
    # ถ้ากด "เล่นต่อ" จะทักใหม่อีกกี่นาที
    "break_snooze_minutes": 30,
    # ถ้าไม่แตะเมาส์/คีย์บอร์ดนานเท่านี้ ถือว่าได้พักแล้ว (เริ่มนับใหม่)
    "break_reset_idle_minutes": 5,
    # ต้องว่าง (ไม่ขยับเมาส์/คีย์บอร์ด) กี่วินาที ถึงจะขึ้นข้อความ
    "idle_wait_seconds": 15,
    # จำกัดความถี่ ไม่ให้เพื่อนจู้จี้
    "max_popups_per_day": 8,
    "min_gap_minutes": 20,
    # ถ้ากดปิด (x) ข้อความเกินเท่านี้ครั้งต่อวัน วันนั้นจะเงียบ
    "max_dismissals_per_day": 3,
    # มื้ออาหาร: [เริ่ม, จบ] เวลา 24 ชั่วโมง
    "meals": {
        "breakfast": ["07:00", "09:30"],
        "lunch": ["11:30", "13:30"],
        "dinner": ["17:30", "19:30"],
    },
    # เปิด/ปิดการทักแต่ละมื้อ
    "meals_enabled": {"breakfast": True, "lunch": True, "dinner": True},
    "meal_snooze_minutes": 30,
    "meal_max_asks": 2,
    # ทักเรื่องนอนตอนดึก
    "late_night": {
        "enabled": True,
        "start": "01:00",
        "end": "05:00",
        "max_asks": 2,
        "snooze_minutes": 60,
    },
    # ตายซ้ำ ๆ (ใช้ได้เมื่อเกมมี death_log ใน games.json)
    "death_streak": {"count": 5, "window_minutes": 20, "snooze_minutes": 30},
    # ข้อความถามที่ไม่มีใครตอบ จะปิดเองหลังกี่วินาที
    "question_timeout_seconds": 300,
    "greeting_timeout_seconds": 10,
    "reply_seconds": 3,
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path) -> dict:
    """อ่าน config.json ถ้าไม่มีไฟล์จะสร้างจากค่าเริ่มต้น"""
    path = Path(path)
    if not path.exists():
        save_config(path, DEFAULTS)
        return copy.deepcopy(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json อ่านไม่ได้ (JSON ผิดรูปแบบ): {exc}") from exc
    if not isinstance(user, dict):
        raise ValueError("config.json ต้องเป็น JSON object")
    return _merge(DEFAULTS, user)


def write_json_atomic(path: Path, data) -> None:
    """เขียนไฟล์ผ่านไฟล์ชั่วคราวก่อนแล้วค่อยแทนที่ ถ้าไฟฟ้าดับกลางทางไฟล์เดิมจะไม่พัง"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_config(path: Path, config: dict) -> None:
    write_json_atomic(path, config)
