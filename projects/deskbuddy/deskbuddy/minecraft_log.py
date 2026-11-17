"""นับจำนวนครั้งที่ตายใน Minecraft Java จากไฟล์ logs/latest.log

อ่านแค่ไฟล์ log ที่เกมเขียนเอง ไม่ยุ่งกับหน่วยความจำหรือไฟล์ของเกม
(ปลอดภัยกับระบบกันโกง) ข้อความตายใน log หน้าตาเช่น
    [12:34:56] [Server thread/INFO]: Steve was slain by Zombie
    [12:34:56] [Render thread/INFO]: [System] [CHAT] Steve fell from a high place
"""

from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path

# วลีที่ตามหลังชื่อผู้เล่นในข้อความตายของเกม (ยังไม่ครบทุกแบบ เพิ่มเองได้)
DEATH_PHRASES = (
    "was slain",
    "was shot",
    "was fireballed",
    "was pummeled",
    "was killed",
    "was blown up",
    "was squashed",
    "was squished",
    "was impaled",
    "was skewered",
    "was poked",
    "was pricked",
    "was stung",
    "was struck by lightning",
    "was burnt",
    "was frozen",
    "was obliterated",
    "was doomed",
    "drowned",
    "experienced kinetic energy",
    "blew up",
    "hit the ground too hard",
    "fell from",
    "fell off",
    "fell out of the world",
    "fell while",
    "went up in flames",
    "burned to death",
    "tried to swim in lava",
    "walked into fire",
    "walked into danger zone",
    "suffocated",
    "starved to death",
    "withered away",
    "froze to death",
    "discovered the floor was lava",
    "died",
    "didn't want to live",
)

_TIME_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]")
_TAG_PREFIX_RE = re.compile(r"^(?:\[[A-Za-z ]+\] )+")  # [System] [CHAT] [Not Secure]


class DeathLogWatcher:
    def __init__(self, path: str, player: str):
        self.path = Path(os.path.expandvars(os.path.expanduser(path)))
        self.player = player.strip()
        self.offset = 0
        self._recent = deque(maxlen=6)  # กันนับซ้ำ (โลกเดี่ยวเขียนทั้งฝั่ง server และ client)

    @property
    def enabled(self) -> bool:
        return bool(self.player)

    def seek_end(self) -> None:
        """เกมเปิดอยู่ก่อนโปรแกรมเริ่ม: ข้ามของเก่า นับเฉพาะที่เกิดหลังจากนี้"""
        try:
            self.offset = self.path.stat().st_size
        except OSError:
            self.offset = 0

    def reset_start(self) -> None:
        """เกมเพิ่งเปิดใหม่: log ไฟล์ใหม่ อ่านตั้งแต่ต้น"""
        self.offset = 0
        self._recent.clear()

    def is_death(self, line: str) -> bool:
        prefix, sep, msg = line.partition("]: ")
        if not sep or "/INFO" not in prefix:
            return False
        msg = _TAG_PREFIX_RE.sub("", msg.strip())
        if not msg.startswith(self.player + " "):
            return False
        rest = msg[len(self.player) + 1 :]
        if not rest.startswith(DEATH_PHRASES):
            return False
        stamp = _TIME_RE.match(line)
        key = (stamp.group(1) if stamp else None, msg)
        if key in self._recent:
            return False
        self._recent.append(key)
        return True

    def poll(self) -> int:
        """คืนจำนวนครั้งที่ตายตั้งแต่ poll ครั้งก่อน"""
        if not self.enabled:
            return 0
        try:
            size = self.path.stat().st_size
        except OSError:
            return 0
        if size < self.offset:  # ไฟล์ถูกสร้างใหม่
            self.offset = 0
        if size == self.offset:
            return 0
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return 0
        last_newline = data.rfind(b"\n")
        if last_newline == -1:  # ยังเขียนบรรทัดไม่จบ
            return 0
        chunk = data[: last_newline + 1]
        self.offset += len(chunk)
        text = chunk.decode("utf-8", errors="replace")
        return sum(1 for line in text.splitlines() if self.is_death(line))
