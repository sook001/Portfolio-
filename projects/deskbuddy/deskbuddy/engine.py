"""ตัวตัดสินใจ: "ตอนนี้ควรทักไหม และทักอะไร"

ไฟล์นี้ไม่แตะ Windows API / หน้าต่าง ทั้งหมดรับค่าเข้ามาเป็นพารามิเตอร์
จึงทดสอบบนเครื่องไหนก็ได้ (ดู tests/test_engine.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional

from .messages import Personality
from .storage import Stats

# ปุ่มที่ใช้ร่วมกันระหว่างป๊อปอัปจริงกับตัวอย่าง (preview) จะได้ตรงกันเสมอ
BREAK_BUTTONS = (("พักก่อน", "rest"), ("เล่นต่อ", "continue"))
NIGHT_BUTTONS = (("กำลังจะนอน", "sleep"), ("ขออีกแป๊บ", "later"))

# ตัวอย่างที่ Engine.preview() สร้างได้ (ชื่อบนปุ่มอยู่ใน settings_model.PREVIEW_GROUPS)
PREVIEW_SCENARIOS = (
    "greeting_morning",
    "greeting_day",
    "greeting_evening",
    "greeting_night",
    "greeting_back",
    "meal_breakfast",
    "meal_lunch",
    "meal_dinner",
    "break",
    "break_again",
    "death",
    "night",
)

# คำตอบของเพื่อนต่อปุ่มแต่ละปุ่ม (ใช้ตอนดูตัวอย่าง)
_REPLY_CONTEXTS = {
    "meal": {"ate": "reply_ate", "not_yet": "reply_not_yet", "snooze": "reply_snooze"},
    "break": {"rest": "reply_rest", "continue": "reply_continue"},
    "death": {"rest": "reply_rest", "continue": "reply_continue"},
    "night": {"sleep": "reply_sleep", "later": "reply_sleep_later"},
}


@dataclass
class PopupRequest:
    kind: str  # greeting | break | death | meal | night | info
    text: str
    buttons: list  # [(ข้อความบนปุ่ม, choice_id), ...]
    context: dict = field(default_factory=dict)
    timeout_seconds: Optional[float] = None


@dataclass
class Session:
    started: datetime
    next_break_at: float  # วินาทีของ active_run ที่จะถามพัก
    active_run: float = 0.0  # เวลาเล่นต่อเนื่อง (รีเซ็ตเมื่อปล่อยว่างนาน)
    break_count: int = 0
    death_snooze_until: Optional[datetime] = None


def fmt_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours} ชั่วโมง {minutes} นาที"
    if hours:
        return f"{hours} ชั่วโมง"
    return f"{max(minutes, 1)} นาที"


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_window(now: time, start: time, end: time) -> bool:
    """รองรับช่วงที่ข้ามเที่ยงคืน เช่น 23:00-05:00"""
    if start <= end:
        return start <= now < end
    return now >= start or now < end


class Engine:
    def __init__(self, config: dict, stats: Stats, personality: Personality, now: datetime | None = None):
        self.cfg = config
        self.stats = stats
        self.msg = personality
        now = now or datetime.now()
        self.started_at = now
        self.gap_days = stats.days_since_last_seen(now.date())
        self.last_tick: Optional[datetime] = None
        self.last_popup_at: Optional[datetime] = None
        self.greeted = False
        self.popup_open = False
        self.paused_until: Optional[datetime] = None
        self.sessions: dict = {}
        self.deaths: dict = {}  # ชื่อเกม -> [เวลาที่ตาย]

    # ------------------------------------------------------------------
    # ค่าที่ใช้บ่อย
    # ------------------------------------------------------------------
    @property
    def _break_after(self) -> float:
        return self.cfg["break_after_minutes"] * 60.0

    def pause(self, minutes: float, now: datetime | None = None) -> None:
        now = now or datetime.now()
        self.paused_until = now + timedelta(minutes=minutes)

    def resume(self) -> None:
        self.paused_until = None

    def record_death(self, game: str, now: datetime) -> None:
        self.deaths.setdefault(game, []).append(now)
        self.stats.add_death(game, now.date())

    # ------------------------------------------------------------------
    # วนทุกรอบสแกน
    # ------------------------------------------------------------------
    def tick(self, now: datetime, running: set, idle: float) -> list:
        """คืนรายการป๊อปอัปที่ควรแสดงตอนนี้ (สูงสุด 1 รายการ)"""
        dt = 0.0
        if self.last_tick is not None:
            dt = (now - self.last_tick).total_seconds()
            limit = max(30.0, self.cfg["scan_interval_seconds"] * 3)
            if dt < 0 or dt > limit:  # เครื่องหลับ/นาฬิกากระโดด ไม่นับ
                dt = 0.0
        self.last_tick = now
        self.stats.touch(now.date())

        self._update_sessions(now, dt, running, idle)

        if self.popup_open:
            return []
        request = self._decide(now, running, idle)
        return [request] if request else []

    def _update_sessions(self, now: datetime, dt: float, running: set, idle: float) -> None:
        reset_idle = self.cfg["break_reset_idle_minutes"] * 60.0
        for name in running:
            session = self.sessions.get(name)
            if session is None:
                session = Session(started=now, next_break_at=self._break_after)
                self.sessions[name] = session
                self.stats.add_session(name)
            self.stats.add_play(name, dt, now.date())
            if idle >= reset_idle:
                # ปล่อยว่างนาน = ได้พักแล้ว เริ่มนับใหม่
                session.active_run = 0.0
                session.next_break_at = self._break_after
                session.break_count = 0
            else:
                session.active_run += dt
        for name in [n for n in self.sessions if n not in running]:
            del self.sessions[name]
            self.deaths.pop(name, None)

    # ------------------------------------------------------------------
    # ตัดสินใจ
    # ------------------------------------------------------------------
    def _decide(self, now: datetime, running: set, idle: float) -> Optional[PopupRequest]:
        if self.paused_until and now < self.paused_until:
            return None
        self.paused_until = None

        if not self.greeted:
            delay = self.cfg["startup_greeting_delay_seconds"]
            if (now - self.started_at).total_seconds() >= delay:
                self.greeted = True
                return self._issue(self._greeting(now), now)
            return None

        if not self._can_popup(now, idle):
            return None

        for builder in (self._break_request, self._death_request, self._meal_request, self._night_request):
            request = builder(now, running)
            if request:
                return self._issue(request, now)
        return None

    def _can_popup(self, now: datetime, idle: float) -> bool:
        day = self.stats.day(now.date())
        if day["popups"] >= self.cfg["max_popups_per_day"]:
            return False
        if day["dismissed"] >= self.cfg["max_dismissals_per_day"]:
            return False
        if idle < self.cfg["idle_wait_seconds"]:
            return False
        if self.last_popup_at is not None:
            if now - self.last_popup_at < timedelta(minutes=self.cfg["min_gap_minutes"]):
                return False
        return True

    def _issue(self, request: PopupRequest, now: datetime) -> PopupRequest:
        self.popup_open = True
        self.last_popup_at = now
        self.stats.count_popup(now.date())
        return request

    # ---------- ทักทายตอนเปิดเครื่อง ----------
    def _greeting(self, now: datetime) -> PopupRequest:
        hour = now.hour
        if self.gap_days >= 3:
            context = "greeting_back"
        elif 5 <= hour < 11:
            context = "greeting_morning"
        elif 11 <= hour < 17:
            context = "greeting_day"
        elif 17 <= hour < 21:
            context = "greeting_evening"
        else:
            context = "greeting_night"
        return PopupRequest(
            kind="greeting",
            text=self.msg.pick(context),
            buttons=[("สวัสดี", "ok")],
            timeout_seconds=self.cfg["greeting_timeout_seconds"],
        )

    # ---------- พักจากเกม ----------
    def _break_request(self, now: datetime, running: set) -> Optional[PopupRequest]:
        best_name, best = None, None
        for name, session in self.sessions.items():
            if session.active_run >= session.next_break_at:
                if best is None or session.active_run > best.active_run:
                    best_name, best = name, session
        if best is None:
            return None
        context = "break_again" if best.break_count else "break"
        text = self.msg.pick(context, game=best_name, duration=fmt_duration(best.active_run))
        return PopupRequest(
            kind="break",
            text=text,
            buttons=list(BREAK_BUTTONS),
            context={"game": best_name},
            timeout_seconds=self.cfg["question_timeout_seconds"],
        )

    # ---------- ตายซ้ำ ๆ ----------
    def _death_request(self, now: datetime, running: set) -> Optional[PopupRequest]:
        cfg = self.cfg["death_streak"]
        window = timedelta(minutes=cfg["window_minutes"])
        for name, session in self.sessions.items():
            recent = [t for t in self.deaths.get(name, []) if now - t <= window]
            self.deaths[name] = recent
            if len(recent) < cfg["count"]:
                continue
            if session.death_snooze_until and now < session.death_snooze_until:
                continue
            session.death_snooze_until = now + timedelta(minutes=cfg["snooze_minutes"])
            self.deaths[name] = []
            return PopupRequest(
                kind="death",
                text=self.msg.pick("death_streak", game=name, count=len(recent)),
                buttons=list(BREAK_BUTTONS),
                context={"game": name},
                timeout_seconds=self.cfg["question_timeout_seconds"],
            )
        return None

    # ---------- มื้ออาหาร (ถามตอนไม่ได้เล่นเกมเท่านั้น) ----------
    def _meal_buttons(self) -> list:
        minutes = self.cfg["meal_snooze_minutes"]
        return [("กินแล้ว", "ate"), ("ยังไม่ได้กิน", "not_yet"), (f"เตือนอีก {minutes} นาที", "snooze")]

    def _meal_request(self, now: datetime, running: set) -> Optional[PopupRequest]:
        if running:
            return None
        enabled = self.cfg.get("meals_enabled", {})
        for meal, (start, end) in self.cfg["meals"].items():
            if not enabled.get(meal, True):
                continue
            if not in_window(now.time(), parse_hhmm(start), parse_hhmm(end)):
                continue
            slot = self.stats.slot(f"{now.date().isoformat()}:meal:{meal}")
            if slot["state"] == "done" or slot["asked"] >= self.cfg["meal_max_asks"]:
                continue
            if slot["snooze_until"] and now < datetime.fromisoformat(slot["snooze_until"]):
                continue
            slot["asked"] += 1
            self.stats.dirty = True
            return PopupRequest(
                kind="meal",
                text=self.msg.pick(f"meal_{meal}"),
                buttons=self._meal_buttons(),
                context={"meal": meal},
                timeout_seconds=self.cfg["question_timeout_seconds"],
            )
        return None

    # ---------- ดึกแล้ว ----------
    def _night_key(self, now: datetime) -> str:
        # คืนเดียวกันใช้คีย์เดียวกัน แม้ข้ามเที่ยงคืน
        return (now - timedelta(hours=12)).date().isoformat() + ":night"

    def _night_request(self, now: datetime, running: set) -> Optional[PopupRequest]:
        cfg = self.cfg["late_night"]
        if not cfg["enabled"]:
            return None
        if not in_window(now.time(), parse_hhmm(cfg["start"]), parse_hhmm(cfg["end"])):
            return None
        slot = self.stats.slot(self._night_key(now))
        if slot["state"] == "done" or slot["asked"] >= cfg["max_asks"]:
            return None
        if slot["snooze_until"] and now < datetime.fromisoformat(slot["snooze_until"]):
            return None
        slot["asked"] += 1
        self.stats.dirty = True
        return PopupRequest(
            kind="night",
            text=self.msg.pick("late_night"),
            buttons=list(NIGHT_BUTTONS),
            timeout_seconds=self.cfg["question_timeout_seconds"],
        )

    # ------------------------------------------------------------------
    # รับคำตอบจากผู้ใช้ -> คืนข้อความตอบกลับ (หรือ None)
    # ------------------------------------------------------------------
    def answer(self, request: PopupRequest, choice: str, now: datetime | None = None) -> Optional[str]:
        now = now or datetime.now()
        self.popup_open = False
        # ปิดคำทัก/สถิติด้วย × ไม่นับว่ารำคาญ นับเฉพาะตอนที่เพื่อน "ถาม" แล้วถูกปัดทิ้ง
        if choice == "dismiss" and request.kind not in ("greeting", "info"):
            self.stats.count_dismissal(now.date())

        kind = request.kind
        if kind == "break":
            return self._answer_break(request, choice)
        if kind == "death":
            return self._answer_death(request, choice)
        if kind == "meal":
            return self._answer_meal(request, choice, now)
        if kind == "night":
            return self._answer_night(choice, now)
        return None  # greeting / info

    def _answer_break(self, request: PopupRequest, choice: str) -> Optional[str]:
        session = self.sessions.get(request.context.get("game"))
        if session:
            session.break_count += 1
            if choice == "rest":
                session.next_break_at = session.active_run + self._break_after
            else:  # continue / dismiss / timeout
                session.next_break_at = session.active_run + self.cfg["break_snooze_minutes"] * 60.0
        if choice == "rest":
            return self.msg.pick("reply_rest")
        if choice == "continue":
            return self.msg.pick("reply_continue")
        return None

    def _answer_death(self, request: PopupRequest, choice: str) -> Optional[str]:
        if choice == "rest":
            return self.msg.pick("reply_rest")
        if choice == "continue":
            return self.msg.pick("reply_continue")
        return None

    def _answer_meal(self, request: PopupRequest, choice: str, now: datetime) -> Optional[str]:
        slot = self.stats.slot(f"{now.date().isoformat()}:meal:{request.context['meal']}")
        self.stats.dirty = True
        if choice == "ate":
            slot["state"] = "done"
            return self.msg.pick("reply_ate")
        slot["snooze_until"] = (now + timedelta(minutes=self.cfg["meal_snooze_minutes"])).isoformat()
        if choice == "not_yet":
            return self.msg.pick("reply_not_yet")
        if choice == "snooze":
            return self.msg.pick("reply_snooze")
        return None

    def _answer_night(self, choice: str, now: datetime) -> Optional[str]:
        slot = self.stats.slot(self._night_key(now))
        self.stats.dirty = True
        if choice == "sleep":
            slot["state"] = "done"
            return self.msg.pick("reply_sleep")
        slot["snooze_until"] = (now + timedelta(minutes=self.cfg["late_night"]["snooze_minutes"])).isoformat()
        if choice == "later":
            return self.msg.pick("reply_sleep_later")
        return None

    # ------------------------------------------------------------------
    # ตัวอย่างป๊อปอัป (ปุ่มทดสอบ) ไม่แตะสถิติ ตัวนับ หรือเวลาเตือนจริง
    # ------------------------------------------------------------------
    def preview(self, scenario: str) -> PopupRequest:
        if scenario not in PREVIEW_SCENARIOS:
            raise ValueError(f"ไม่รู้จักตัวอย่าง: {scenario}")
        cfg = self.cfg
        context = {"preview": True}
        timeout = 60.0  # ตัวอย่างปิดเองเร็วกว่าของจริง
        game = "Minecraft"

        if scenario.startswith("greeting_"):
            return PopupRequest("greeting", self.msg.pick(scenario), [("สวัสดี", "ok")], context, timeout)
        if scenario.startswith("meal_"):
            return PopupRequest("meal", self.msg.pick(scenario), self._meal_buttons(), context, timeout)
        if scenario == "break":
            text = self.msg.pick("break", game=game, duration=fmt_duration(cfg["break_after_minutes"] * 60.0))
            return PopupRequest("break", text, list(BREAK_BUTTONS), dict(context, game=game), timeout)
        if scenario == "break_again":
            seconds = (cfg["break_after_minutes"] + cfg["break_snooze_minutes"]) * 60.0
            text = self.msg.pick("break_again", game=game, duration=fmt_duration(seconds))
            return PopupRequest("break", text, list(BREAK_BUTTONS), dict(context, game=game), timeout)
        if scenario == "death":
            text = self.msg.pick("death_streak", game=game, count=cfg["death_streak"]["count"])
            return PopupRequest("death", text, list(BREAK_BUTTONS), dict(context, game=game), timeout)
        return PopupRequest("night", self.msg.pick("late_night"), list(NIGHT_BUTTONS), context, timeout)

    def preview_reply(self, request: PopupRequest, choice: str) -> Optional[str]:
        """ข้อความที่เพื่อนตอบหลังกดปุ่มในตัวอย่าง (ไม่บันทึกอะไร)"""
        reply_context = _REPLY_CONTEXTS.get(request.kind, {}).get(choice)
        return self.msg.pick(reply_context) if reply_context else None

    # ------------------------------------------------------------------
    # สรุปวันนี้ (เมนู tray)
    # ------------------------------------------------------------------
    def today_summary(self, now: datetime | None = None) -> PopupRequest:
        now = now or datetime.now()
        played = self.stats.played_today(now.date())
        if not played:
            text = "วันนี้ยังไม่ได้เล่นเกมเลยนะ"
        else:
            lines = ["วันนี้เล่นเกมไปแล้ว"]
            for name, (seconds, deaths) in sorted(played.items(), key=lambda kv: -kv[1][0]):
                line = f"• {name}: {fmt_duration(seconds)}"
                if deaths:
                    line += f" (ตาย {deaths} ครั้ง)"
                lines.append(line)
            text = "\n".join(lines)
        return PopupRequest(kind="info", text=text, buttons=[("โอเค", "ok")], timeout_seconds=20)
