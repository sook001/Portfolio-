"""ตัวประกอบทุกส่วนเข้าด้วยกัน: tray + ลูปตรวจสถานะ + ป๊อปอัป

ทุกอย่างทำงานในเธรดหลักของ tkinter ผ่าน root.after() ส่วนเมนู tray (pystray)
รันอีกเธรดและส่งคำสั่งเข้ามาทาง queue จึงไม่มีการแตะ tkinter ข้ามเธรด
"""

from __future__ import annotations

import json
import logging
import queue
import time
import tkinter as tk
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox

from . import autostart, winapi
from .config import load_config, save_config
from .engine import Engine, PopupRequest
from .games import detect, load_games, save_games
from .messages import Personality
from .minecraft_log import DeathLogWatcher
from .settings_model import list_personalities
from .settings_window import SettingsWindow
from .storage import Stats
from .ui import Popup, make_tray_icon_image

log = logging.getLogger("deskbuddy")

POLL_MS = 1000
SAVE_EVERY_SECONDS = 60
PAUSE_MINUTES = 60


def _setup_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir / "deskbuddy.log", maxBytes=200_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _fatal(message: str) -> None:
    log.error(message)
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("DeskBuddy", message)
        root.destroy()
    except Exception:
        print(message)


class App:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.cfg = load_config(self.base_dir / "config.json")
        self.games = load_games(self.base_dir / "games.json")
        self.stats = Stats(self.base_dir / "data" / "stats.json")
        personality = Personality.load(
            self.base_dir / "personalities" / f"{self.cfg['personality']}.json",
            user_name=self.cfg["user_name"],
        )
        self.engine = Engine(self.cfg, self.stats, personality)

        self._prev_running = None
        self.watchers: dict = self._build_watchers({})

        self.commands: queue.Queue = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.icon = None
        self.settings_win = None
        self._last_scan = 0.0
        self._last_save = time.monotonic()

    # ------------------------------------------------------------------
    # tray
    # ------------------------------------------------------------------
    def _start_tray(self) -> None:
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("ตั้งค่า…", lambda: self.commands.put("settings"), default=True),
            pystray.MenuItem("ดูสถิติวันนี้", lambda: self.commands.put("stats")),
            pystray.MenuItem(f"พักการแจ้งเตือน {PAUSE_MINUTES} นาที", lambda: self.commands.put("pause")),
            pystray.MenuItem("เปิดการแจ้งเตือนอีกครั้ง", lambda: self.commands.put("resume")),
            pystray.MenuItem(
                "เปิดพร้อม Windows",
                lambda: self.commands.put("toggle_autostart"),
                checked=lambda _item: autostart.is_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ออกจากโปรแกรม", lambda: self.commands.put("quit")),
        )
        self.icon = pystray.Icon("DeskBuddy", make_tray_icon_image(), "DeskBuddy", menu)
        self.icon.run_detached()

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            now = datetime.now()
            if command == "settings":
                self._open_settings()
            elif command == "stats":
                self._show(self.engine.today_summary(now), tracked=False)
            elif command == "pause":
                self.engine.pause(PAUSE_MINUTES, now)
            elif command == "resume":
                self.engine.resume()
            elif command == "toggle_autostart":
                if autostart.is_enabled():
                    autostart.disable()
                else:
                    autostart.enable(self.base_dir / "main.py")
            elif command == "quit":
                self._quit()
                return

    # ------------------------------------------------------------------
    # หน้าตั้งค่า
    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        win = self.settings_win
        if win is not None and win.exists():
            win.focus()
            return
        self.settings_win = SettingsWindow(
            self.root,
            self.cfg,
            self.games,
            list_personalities(self.base_dir / "personalities"),
            autostart.is_enabled(),
            self.apply_settings,
            on_preview=self.show_preview,
        )

    def show_preview(self, scenario: str) -> None:
        """ป๊อปอัปตัวอย่างจากปุ่มทดสอบ: ไม่เรียก engine.answer จึงไม่นับ/ไม่บันทึกอะไร"""
        request = self.engine.preview(scenario)
        Popup(
            self.root,
            request,
            lambda choice: self.engine.preview_reply(request, choice),
            reply_seconds=self.cfg["reply_seconds"],
        )

    def apply_settings(self, new_cfg: dict, new_games: list, autostart_on: bool) -> list:
        """บันทึกลงไฟล์และใช้ค่าใหม่ทันที คืนรายการคำเตือน (ถ้ามี)"""
        warnings: list = []
        # โหลดบุคลิกก่อนเขียนไฟล์ ถ้าไฟล์บุคลิกเสียจะได้ไม่บันทึกค่าที่ใช้ไม่ได้
        personality = Personality.load(
            self.base_dir / "personalities" / f"{new_cfg['personality']}.json",
            user_name=new_cfg["user_name"],
        )
        save_config(self.base_dir / "config.json", new_cfg)
        save_games(self.base_dir / "games.json", new_games)

        self.cfg.clear()  # engine ถือ dict ตัวเดียวกันนี้ จึงเห็นค่าใหม่ทันที
        self.cfg.update(new_cfg)
        self.games = new_games
        self.engine.msg = personality
        self.watchers = self._build_watchers(self.watchers)

        if autostart_on != autostart.is_enabled():
            ok = autostart.enable(self.base_dir / "main.py") if autostart_on else autostart.disable()
            if not ok:
                warnings.append("ตั้งค่าการเปิดพร้อม Windows ไม่สำเร็จ")
        return warnings

    def _build_watchers(self, old: dict) -> dict:
        watchers: dict = {}
        running = self._prev_running or set()
        for game in self.games:
            death_log = game.death_log or {}
            player = str(death_log.get("player", "")).strip()
            if not player:
                continue
            fresh = DeathLogWatcher(death_log.get("path", ""), player)
            previous = old.get(game.name)
            if previous is not None and previous.player == fresh.player and previous.path == fresh.path:
                watchers[game.name] = previous  # ไม่เปลี่ยน เก็บตำแหน่งที่อ่านค้างไว้
            else:
                if game.name in running:
                    fresh.seek_end()  # เกมเปิดอยู่แล้ว ข้ามของเก่า นับเฉพาะหลังจากนี้
                watchers[game.name] = fresh
        return watchers

    def _quit(self) -> None:
        try:
            self.stats.save()
        finally:
            if self.icon is not None:
                self.icon.stop()
            self.root.quit()

    # ------------------------------------------------------------------
    # ลูปหลัก
    # ------------------------------------------------------------------
    def _poll(self) -> None:
        try:
            self._drain_commands()
            now_mono = time.monotonic()
            if now_mono - self._last_scan >= self.cfg["scan_interval_seconds"]:
                self._last_scan = now_mono
                self._scan_once()
            if now_mono - self._last_save >= SAVE_EVERY_SECONDS:
                self._last_save = now_mono
                self.stats.save_if_dirty()
        except Exception:
            log.exception("เกิดข้อผิดพลาดในลูปหลัก")
        self.root.after(POLL_MS, self._poll)

    def _scan_once(self) -> None:
        import psutil

        procs = [(p.info["pid"], p.info.get("name") or "") for p in psutil.process_iter(["pid", "name"])]
        running = detect(self.games, procs, winapi.window_titles)
        now = datetime.now()
        self._update_watchers(running, now)
        self._prev_running = running
        for request in self.engine.tick(now, running, winapi.idle_seconds()):
            self._show(request)

    def _update_watchers(self, running: set, now: datetime) -> None:
        first_scan = self._prev_running is None
        previous = self._prev_running or set()
        for name, watcher in self.watchers.items():
            if name not in running:
                continue
            if name not in previous:
                if first_scan:
                    watcher.seek_end()  # เกมเปิดอยู่ก่อนโปรแกรม: ข้ามของเก่า
                else:
                    watcher.reset_start()  # เกมเพิ่งเปิด: log ใหม่
            for _ in range(watcher.poll()):
                self.engine.record_death(name, now)

    # ------------------------------------------------------------------
    # ป๊อปอัป
    # ------------------------------------------------------------------
    def _show(self, request: PopupRequest, tracked: bool = True) -> None:
        if tracked:

            def on_answer(choice: str):
                return self.engine.answer(request, choice, datetime.now())

        else:

            def on_answer(choice: str):
                return None

        try:
            Popup(self.root, request, on_answer, reply_seconds=self.cfg["reply_seconds"])
        except Exception:
            log.exception("แสดงป๊อปอัปไม่สำเร็จ")
            if tracked:
                self.engine.answer(request, "timeout", datetime.now())

    def run(self) -> None:
        self._start_tray()
        self.root.after(POLL_MS, self._poll)
        log.info("DeskBuddy เริ่มทำงาน")
        self.root.mainloop()
        self.stats.save()
        log.info("DeskBuddy ปิดตัว")


def run(base_dir: Path) -> None:
    base_dir = Path(base_dir)
    _setup_logging(base_dir / "data")
    if not winapi.acquire_single_instance():
        return  # เปิดอยู่แล้ว
    winapi.enable_dpi_awareness()
    try:
        app = App(base_dir)
        app.run()
    except ImportError as exc:
        _fatal(f"ขาดไลบรารี: {exc}\nลองรันคำสั่ง: pip install -r requirements.txt")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        _fatal(f"เริ่มโปรแกรมไม่ได้: {exc}")
