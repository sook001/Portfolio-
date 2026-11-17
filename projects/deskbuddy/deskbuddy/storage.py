"""เก็บสถิติในเครื่อง (data/stats.json) ไม่ส่งออกไปไหน"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

KEEP_DAYS = 90


class Stats:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.dirty = False
        self.data = {"version": 1, "games": {}, "days": {}, "slots": {}, "last_seen": None}
        self._load()

    # ---------- โหลด/บันทึก ----------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for key in self.data:
                    if key in loaded:
                        self.data[key] = loaded[key]
        except (OSError, json.JSONDecodeError):
            # ไฟล์เสีย: เก็บของเก่าไว้เป็น .bak แล้วเริ่มใหม่ ไม่ให้โปรแกรมล้ม
            try:
                os.replace(self.path, self.path.with_suffix(".bak"))
            except OSError:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            self.dirty = False
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def save_if_dirty(self) -> None:
        if self.dirty:
            self.save()

    # ---------- วันที่ ----------
    def days_since_last_seen(self, today: date) -> int:
        last = self.data.get("last_seen")
        if not last:
            return 0
        try:
            return (today - date.fromisoformat(last)).days
        except ValueError:
            return 0

    def touch(self, today: date) -> None:
        iso = today.isoformat()
        if self.data.get("last_seen") != iso:
            self.data["last_seen"] = iso
            self._prune(today)
            self.dirty = True

    def _prune(self, today: date) -> None:
        cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
        for day in [d for d in self.data["days"] if d < cutoff]:
            del self.data["days"][day]
        for slot in [s for s in self.data["slots"] if s.split(":", 1)[0] < cutoff]:
            del self.data["slots"][slot]
        for game in self.data["games"].values():
            for field in ("daily", "deaths_daily"):
                bucket = game.get(field, {})
                for day in [d for d in bucket if d < cutoff]:
                    del bucket[day]

    # ---------- ตัวนับต่อวัน ----------
    def day(self, today: date) -> dict:
        return self.data["days"].setdefault(today.isoformat(), {"popups": 0, "dismissed": 0})

    def count_popup(self, today: date) -> None:
        self.day(today)["popups"] += 1
        self.dirty = True

    def count_dismissal(self, today: date) -> None:
        self.day(today)["dismissed"] += 1
        self.dirty = True

    # ---------- สล็อต (มื้ออาหาร/ดึก) ----------
    def slot(self, key: str) -> dict:
        """key ขึ้นต้นด้วยวันที่ เช่น '2026-11-10:meal:lunch'"""
        return self.data["slots"].setdefault(key, {"asked": 0, "state": None, "snooze_until": None})

    # ---------- เกม ----------
    def _game(self, name: str) -> dict:
        return self.data["games"].setdefault(
            name, {"total_seconds": 0.0, "sessions": 0, "daily": {}, "deaths_daily": {}}
        )

    def add_session(self, name: str) -> None:
        self._game(name)["sessions"] += 1
        self.dirty = True

    def add_play(self, name: str, seconds: float, today: date) -> None:
        if seconds <= 0:
            return
        game = self._game(name)
        game["total_seconds"] += seconds
        iso = today.isoformat()
        game["daily"][iso] = game["daily"].get(iso, 0.0) + seconds
        self.dirty = True

    def add_death(self, name: str, today: date) -> None:
        game = self._game(name)
        iso = today.isoformat()
        game["deaths_daily"][iso] = game["deaths_daily"].get(iso, 0) + 1
        self.dirty = True

    def played_today(self, today: date) -> dict:
        """{ชื่อเกม: (วินาทีที่เล่นวันนี้, จำนวนครั้งที่ตายวันนี้)}"""
        iso = today.isoformat()
        out = {}
        for name, game in self.data["games"].items():
            seconds = game.get("daily", {}).get(iso, 0.0)
            deaths = game.get("deaths_daily", {}).get(iso, 0)
            if seconds > 0 or deaths > 0:
                out[name] = (seconds, deaths)
        return out
