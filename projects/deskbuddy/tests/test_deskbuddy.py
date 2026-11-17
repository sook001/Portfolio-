"""ทดสอบตรรกะหลักของ DeskBuddy (ไม่ต้องใช้ Windows หรือหน้าต่าง)

รัน:  python -m unittest discover -s tests -v
"""

import copy
import json
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from deskbuddy.config import DEFAULTS, load_config  # noqa: E402
from deskbuddy.engine import Engine, fmt_duration, in_window  # noqa: E402
from deskbuddy.engine import parse_hhmm  # noqa: E402
from deskbuddy.games import GameDef, detect, load_games  # noqa: E402
from deskbuddy.messages import REQUIRED_CONTEXTS, Personality  # noqa: E402
from deskbuddy.minecraft_log import DeathLogWatcher  # noqa: E402
from deskbuddy.storage import Stats  # noqa: E402

PERSONALITY_FILE = ROOT / "personalities" / "friendly.json"
MC = {"Minecraft"}


def make_engine(tmp, start, user_name="", **overrides):
    cfg = copy.deepcopy(DEFAULTS)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    stats = Stats(Path(tmp) / "stats.json")
    personality = Personality.load(PERSONALITY_FILE, user_name=user_name, rng=random.Random(1))
    return Engine(cfg, stats, personality, now=start), stats


def advance(engine, t, seconds, running=frozenset(), idle=0.0, step=5, stop_on_request=True):
    """เดินเวลาไปข้างหน้าทีละ step วินาที คืน (เวลาปัจจุบัน, [(เวลา, request), ...])"""
    found = []
    for _ in range(int(seconds / step)):
        t += timedelta(seconds=step)
        for request in engine.tick(t, set(running), idle):
            found.append((t, request))
        if found and stop_on_request:
            break
    return t, found


def greet(engine, t):
    """เดินไปจนทักทายแล้วกดปุ่มสวัสดี"""
    t, found = advance(engine, t, 60)
    assert found and found[0][1].kind == "greeting", found
    engine.answer(found[0][1], "ok", t)
    return t


class HelperTests(unittest.TestCase):
    def test_fmt_duration(self):
        self.assertEqual(fmt_duration(30), "1 นาที")
        self.assertEqual(fmt_duration(45 * 60), "45 นาที")
        self.assertEqual(fmt_duration(2 * 3600), "2 ชั่วโมง")
        self.assertEqual(fmt_duration(2 * 3600 + 10 * 60 + 5), "2 ชั่วโมง 10 นาที")

    def test_in_window(self):
        self.assertTrue(in_window(parse_hhmm("12:00"), parse_hhmm("11:30"), parse_hhmm("13:30")))
        self.assertFalse(in_window(parse_hhmm("13:30"), parse_hhmm("11:30"), parse_hhmm("13:30")))
        # ข้ามเที่ยงคืน
        self.assertTrue(in_window(parse_hhmm("23:30"), parse_hhmm("23:00"), parse_hhmm("05:00")))
        self.assertTrue(in_window(parse_hhmm("02:00"), parse_hhmm("23:00"), parse_hhmm("05:00")))
        self.assertFalse(in_window(parse_hhmm("12:00"), parse_hhmm("23:00"), parse_hhmm("05:00")))


class ConfigAndDataFileTests(unittest.TestCase):
    def test_config_created_and_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = load_config(path)  # ไม่มีไฟล์ -> สร้างให้
            self.assertTrue(path.exists())
            self.assertEqual(cfg["break_after_minutes"], 120)
            path.write_text(json.dumps({"break_after_minutes": 180, "meals": {"lunch": ["12:00", "13:00"]}}))
            cfg = load_config(path)
            self.assertEqual(cfg["break_after_minutes"], 180)
            self.assertEqual(cfg["meals"]["lunch"], ["12:00", "13:00"])
            self.assertIn("dinner", cfg["meals"])  # ค่าที่ไม่ได้ระบุยังอยู่

    def test_bad_config_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{ not json")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_shipped_games_json_loads(self):
        games = load_games(ROOT / "games.json")
        names = [g.name for g in games]
        self.assertIn("Minecraft", names)
        mc = next(g for g in games if g.name == "Minecraft")
        self.assertEqual(mc.processes, ["javaw.exe"])
        self.assertEqual(mc.window_contains, "Minecraft")

    def test_stats_roundtrip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            day = datetime(2026, 11, 10).date()
            s = Stats(path)
            s.add_session("Minecraft")
            s.add_play("Minecraft", 90, day)
            s.add_death("Minecraft", day)
            s.save()
            s2 = Stats(path)
            self.assertEqual(s2.played_today(day), {"Minecraft": (90.0, 1)})
            path.write_text("garbage{{")
            s3 = Stats(path)  # ต้องไม่ล้ม
            self.assertEqual(s3.played_today(day), {})
            self.assertTrue(path.with_suffix(".bak").exists())


class PersonalityTests(unittest.TestCase):
    def test_every_message_formats_cleanly(self):
        data = json.loads(PERSONALITY_FILE.read_text(encoding="utf-8"))
        variables = {"game": "Minecraft", "duration": "2 ชั่วโมง", "count": 5, "name": "สุข"}
        for context, options in data["messages"].items():
            self.assertTrue(options, context)
            for text in options:
                formatted = text.format(**variables)  # ถ้ามีวงเล็บปีกกาผิดจะ error ตรงนี้
                self.assertNotIn("{", formatted)

    def test_every_context_has_a_message_without_name(self):
        p = Personality.load(PERSONALITY_FILE, user_name="")
        for context in REQUIRED_CONTEXTS:
            text = p.pick(context, game="Minecraft", duration="2 ชั่วโมง", count=5)
            self.assertTrue(text, context)
            self.assertNotIn("{", text)

    def test_no_immediate_repeat(self):
        p = Personality.load(PERSONALITY_FILE, user_name="", rng=random.Random(3))
        previous = None
        for _ in range(40):
            text = p.pick("greeting_morning")
            self.assertNotEqual(text, previous)
            previous = text

    def test_missing_context_is_rejected(self):
        with self.assertRaises(ValueError):
            Personality({"messages": {"break": ["x"]}})


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.games = [
            GameDef("Minecraft", ["javaw.exe"], window_contains="Minecraft"),
            GameDef("Counter-Strike 2", ["cs2.exe"]),
        ]

    def test_process_name_case_insensitive(self):
        self.assertEqual(detect(self.games, [(5, "CS2.EXE")], lambda pids: {}), {"Counter-Strike 2"})

    def test_javaw_needs_minecraft_window(self):
        procs = [(1, "javaw.exe"), (2, "chrome.exe")]
        self.assertEqual(detect(self.games, procs, lambda pids: {1: ["Minecraft* 1.21.1"]}), {"Minecraft"})
        # javaw ของโปรแกรม Java อื่นต้องไม่ถูกนับเป็น Minecraft
        self.assertEqual(detect(self.games, procs, lambda pids: {1: ["IntelliJ IDEA"]}), set())
        self.assertEqual(detect(self.games, procs, lambda pids: {}), set())

    def test_window_lookup_skipped_when_process_absent(self):
        def boom(pids):
            raise AssertionError("ไม่ควรเรียกเมื่อไม่มี process")

        self.assertEqual(detect(self.games, [(2, "chrome.exe")], boom), set())


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self.tmpdir.name
        self.t0 = datetime(2026, 11, 10, 10, 0, 0)  # 10:00 ไม่อยู่ในช่วงมื้ออาหาร/ดึก

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------- ทักทาย ----------
    def test_greeting_once_after_delay(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t, found = advance(engine, self.t0, 10)
        self.assertEqual(found, [])  # ยังไม่ครบ 15 วินาที
        t, found = advance(engine, t, 30)
        self.assertEqual(found[0][1].kind, "greeting")
        engine.answer(found[0][1], "ok", t)
        t, found = advance(engine, t, 600, idle=60)
        self.assertEqual(found, [])  # ไม่ทักทายซ้ำ

    def test_greeting_back_after_days_away(self):
        stats_path = Path(self.tmp) / "stats.json"
        old = Stats(stats_path)
        old.touch((self.t0 - timedelta(days=5)).date())
        old.save()
        engine, _ = make_engine(self.tmp, self.t0)
        _, found = advance(engine, self.t0, 30)
        self.assertEqual(found[0][1].kind, "greeting")
        self.assertEqual(engine.gap_days, 5)

    def test_closing_greeting_with_x_is_not_a_dismissal(self):
        engine, stats = make_engine(self.tmp, self.t0)
        t, found = advance(engine, self.t0, 30)
        engine.answer(found[0][1], "dismiss", t)
        self.assertEqual(stats.day(t.date())["dismissed"], 0)

    # ---------- พักจากเกม ----------
    def test_break_waits_for_idle_then_asks(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        # เล่นเกิน 2 ชั่วโมงโดยไม่ว่างเลย -> ต้องไม่มีป๊อปอัปขัดจังหวะ
        t, found = advance(engine, t, 2 * 3600 + 600, running=MC, idle=0.0)
        self.assertEqual(found, [])
        self.assertGreaterEqual(engine.sessions["Minecraft"].active_run, 2 * 3600)
        # พอว่างเกินเกณฑ์ ถึงจะถาม
        t, found = advance(engine, t, 30, running=MC, idle=20.0)
        self.assertEqual(found[0][1].kind, "break")
        self.assertIn("ชั่วโมง", found[0][1].text)

    def test_idle_below_wait_threshold_does_not_ask(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, found = advance(engine, t, 2 * 3600 + 600, running=MC, idle=0.0)
        t, found = advance(engine, t, 60, running=MC, idle=10.0)  # น้อยกว่า 15 วินาที
        self.assertEqual(found, [])

    def test_continue_snoozes_then_asks_again(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 2 * 3600 + 60, running=MC, idle=0.0)
        t, found = advance(engine, t, 30, running=MC, idle=20.0)
        request = found[0][1]
        reply = engine.answer(request, "continue", t)
        self.assertTrue(reply)
        # 20 นาทีต่อมายังไม่ถาม (ต้องรอ 30 นาทีของเวลาเล่น)
        t, found = advance(engine, t, 20 * 60, running=MC, idle=0.0)
        t, found = advance(engine, t, 60, running=MC, idle=20.0)
        self.assertEqual(found, [])
        # ครบ 30 นาที -> ถามอีกด้วยข้อความชุด "break_again"
        t, _ = advance(engine, t, 12 * 60, running=MC, idle=0.0)
        t, found = advance(engine, t, 60, running=MC, idle=20.0)
        self.assertEqual(found[0][1].kind, "break")
        self.assertEqual(engine.sessions["Minecraft"].break_count, 1)

    def test_long_idle_counts_as_break(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 90 * 60, running=MC, idle=0.0)
        before = engine.sessions["Minecraft"].active_run
        self.assertGreater(before, 80 * 60)
        t, _ = advance(engine, t, 10, running=MC, idle=400.0)  # ปล่อยว่าง 6+ นาที
        self.assertEqual(engine.sessions["Minecraft"].active_run, 0.0)
        # เล่นอีก 90 นาทีก็ยังไม่ถึงเกณฑ์ 2 ชั่วโมง
        t, found = advance(engine, t, 90 * 60, running=MC, idle=0.0)
        t, found = advance(engine, t, 60, running=MC, idle=20.0)
        self.assertEqual(found, [])

    def test_play_time_tracked_per_game_and_session_ends(self):
        engine, stats = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 600, running=MC, idle=0.0)
        self.assertAlmostEqual(stats.played_today(t.date())["Minecraft"][0], 600, delta=10)
        t, _ = advance(engine, t, 60, running=set(), idle=0.0)
        self.assertNotIn("Minecraft", engine.sessions)

    def test_sleep_gap_is_not_counted_as_play_time(self):
        engine, stats = make_engine(self.tmp, self.t0)
        engine.tick(self.t0 + timedelta(seconds=5), MC, 0.0)
        engine.tick(self.t0 + timedelta(seconds=10), MC, 0.0)
        engine.tick(self.t0 + timedelta(hours=3), MC, 0.0)  # เครื่องหลับไป 3 ชั่วโมง
        engine.tick(self.t0 + timedelta(hours=3, seconds=5), MC, 0.0)
        seconds = stats.played_today(self.t0.date())["Minecraft"][0]
        self.assertEqual(seconds, 10.0)  # นับ 5 วินาทีก่อนหลับกับ 5 วินาทีหลังตื่น ช่วงหลับ 3 ชั่วโมงไม่นับ

    # ---------- ตายซ้ำ ----------
    def test_death_streak_asks_once_then_snoozes(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 25 * 60, running=MC, idle=0.0)  # ผ่านช่วง min_gap
        for i in range(5):
            engine.record_death("Minecraft", t - timedelta(minutes=5 - i))
        t, found = advance(engine, t, 30, running=MC, idle=20.0)
        self.assertEqual(found[0][1].kind, "death")
        self.assertIn("5", found[0][1].text)
        engine.answer(found[0][1], "continue", t)
        for i in range(5):
            engine.record_death("Minecraft", t + timedelta(seconds=i))
        t, found = advance(engine, t, 25 * 60, running=MC, idle=20.0)
        self.assertEqual(found, [])  # ยังอยู่ในช่วง snooze 30 นาที

    def test_old_deaths_outside_window_do_not_count(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 25 * 60, running=MC, idle=0.0)
        for i in range(5):
            engine.record_death("Minecraft", t - timedelta(minutes=60 + i))
        t, found = advance(engine, t, 60, running=MC, idle=20.0)
        self.assertEqual(found, [])

    # ---------- มื้ออาหาร ----------
    def test_lunch_asked_once_after_ate(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        engine, _ = make_engine(self.tmp, start)
        t = greet(engine, start)
        t, found = advance(engine, t, 25 * 60, idle=30.0)
        request = found[0][1]
        self.assertEqual((request.kind, request.context["meal"]), ("meal", "lunch"))
        engine.answer(request, "ate", t)
        t, found = advance(engine, t, 3600, idle=30.0)
        self.assertEqual(found, [])

    def test_not_yet_snoozes_and_asks_at_most_twice(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        engine, _ = make_engine(self.tmp, start)
        t = greet(engine, start)
        t, found = advance(engine, t, 25 * 60, idle=30.0)
        engine.answer(found[0][1], "not_yet", t)
        t, found = advance(engine, t, 20 * 60, idle=30.0)
        self.assertEqual(found, [])  # ยังไม่ครบ 30 นาที
        t, found = advance(engine, t, 15 * 60, idle=30.0)
        self.assertEqual(found[0][1].kind, "meal")
        engine.answer(found[0][1], "snooze", t)
        t, found = advance(engine, t, 40 * 60, idle=30.0)
        self.assertEqual(found, [])  # ถามครบ 2 ครั้งแล้ว หยุด

    def test_no_meal_question_while_gaming(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        engine, _ = make_engine(self.tmp, start)
        t = greet(engine, start)
        t, found = advance(engine, t, 60 * 60, running=MC, idle=30.0)
        self.assertEqual([r.kind for _, r in found if r.kind == "meal"], [])

    def test_meal_not_asked_without_idle(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        engine, _ = make_engine(self.tmp, start)
        t = greet(engine, start)
        t, found = advance(engine, t, 60 * 60, idle=1.0)
        self.assertEqual(found, [])

    # ---------- ดึก ----------
    def test_late_night_asks_then_stops_after_sleep(self):
        start = datetime(2026, 11, 10, 1, 59, 50)
        engine, _ = make_engine(self.tmp, start)
        t = greet(engine, start)
        t, found = advance(engine, t, 25 * 60, idle=30.0)
        self.assertEqual(found[0][1].kind, "night")
        engine.answer(found[0][1], "sleep", t)
        t, found = advance(engine, t, 2 * 3600, idle=30.0)
        self.assertEqual(found, [])

    def test_late_night_window_across_midnight_is_one_night(self):
        engine, _ = make_engine(self.tmp, datetime(2026, 11, 10, 23, 30), late_night={"start": "23:00", "end": "05:00"})
        a = engine._night_key(datetime(2026, 11, 10, 23, 50))
        b = engine._night_key(datetime(2026, 11, 11, 2, 0))
        self.assertEqual(a, b)

    def test_late_night_can_be_disabled(self):
        start = datetime(2026, 11, 10, 1, 59, 50)
        engine, _ = make_engine(self.tmp, start, late_night={"enabled": False})
        t = greet(engine, start)
        t, found = advance(engine, t, 2 * 3600, idle=30.0)
        self.assertEqual(found, [])

    # ---------- ไม่จู้จี้ ----------
    def test_daily_popup_cap(self):
        engine, _ = make_engine(self.tmp, self.t0, max_popups_per_day=1)
        t = greet(engine, self.t0)  # ทักทายนับเป็น 1
        t, found = advance(engine, t, 2 * 3600 + 600, running=MC, idle=0.0)
        t, found = advance(engine, t, 60, running=MC, idle=30.0)
        self.assertEqual(found, [])

    def test_three_dismissals_silence_the_day(self):
        engine, stats = make_engine(self.tmp, self.t0, break_after_minutes=30, break_snooze_minutes=1, min_gap_minutes=0)
        t = greet(engine, self.t0)
        t, _ = advance(engine, t, 31 * 60, running=MC, idle=0.0)
        for _ in range(3):
            t, found = advance(engine, t, 120, running=MC, idle=30.0)
            self.assertEqual(found[0][1].kind, "break")
            engine.answer(found[0][1], "dismiss", t)
            t, _ = advance(engine, t, 90, running=MC, idle=0.0)
        self.assertEqual(stats.day(t.date())["dismissed"], 3)
        t, found = advance(engine, t, 600, running=MC, idle=30.0)
        self.assertEqual(found, [])

    def test_min_gap_between_popups(self):
        engine, _ = make_engine(self.tmp, self.t0, break_after_minutes=1)
        t = greet(engine, self.t0)
        t, found = advance(engine, t, 5 * 60, running=MC, idle=0.0)
        t, found = advance(engine, t, 5 * 60, running=MC, idle=30.0)
        self.assertEqual(found, [])  # ผ่านไปแค่ ~10 นาทีหลังทักทาย ยังไม่ถึง min_gap 20 นาที

    def test_pause_blocks_everything_then_expires(self):
        engine, _ = make_engine(self.tmp, self.t0)
        engine.pause(60, self.t0)
        t, found = advance(engine, self.t0, 30 * 60, idle=30.0)
        self.assertEqual(found, [])
        t, found = advance(engine, t, 40 * 60, idle=30.0)
        self.assertEqual(found[0][1].kind, "greeting")

    def test_only_one_popup_open_at_a_time(self):
        engine, _ = make_engine(self.tmp, self.t0)
        t, found = advance(engine, self.t0, 30)  # ทักทายเปิดค้างไว้ ไม่ตอบ
        self.assertTrue(engine.popup_open)
        t, found = advance(engine, t, 3 * 3600, running=MC, idle=30.0)
        self.assertEqual(found, [])

    def test_today_summary(self):
        engine, stats = make_engine(self.tmp, self.t0)
        self.assertIn("ยังไม่ได้เล่น", engine.today_summary(self.t0).text)
        stats.add_play("Minecraft", 3900, self.t0.date())
        stats.add_death("Minecraft", self.t0.date())
        text = engine.today_summary(self.t0).text
        self.assertIn("Minecraft", text)
        self.assertIn("1 ชั่วโมง 5 นาที", text)
        self.assertIn("ตาย 1 ครั้ง", text)


class DeathLogTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "latest.log"

    def tearDown(self):
        self.tmpdir.cleanup()

    def write(self, text, mode="w"):
        with open(self.path, mode, encoding="utf-8", newline="") as f:
            f.write(text)

    def test_counts_deaths_and_ignores_noise(self):
        self.write(
            "[12:00:00] [Server thread/INFO]: Steve joined the game\n"
            "[12:00:05] [Server thread/INFO]: Steve was slain by Zombie\n"
            "[12:00:05] [Render thread/INFO]: [System] [CHAT] Steve was slain by Zombie\n"  # ซ้ำ (โลกเดี่ยว)
            "[12:00:10] [Render thread/INFO]: [CHAT] <Steve> I died lol\n"  # แชต ไม่ใช่การตาย
            "[12:00:20] [Server thread/INFO]: Alex fell from a high place\n"  # ผู้เล่นอื่น
            "[12:00:30] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve fell from a high place\n"
            "[12:00:40] [Server thread/INFO]: Steve has made the advancement [Stone Age]\n"
            "[12:00:50] [Server thread/INFO]: Steve drowned\n"
        )
        watcher = DeathLogWatcher(str(self.path), "Steve")
        self.assertEqual(watcher.poll(), 3)
        self.assertEqual(watcher.poll(), 0)  # อ่านซ้ำไม่นับซ้ำ

    def test_player_name_required(self):
        self.write("[12:00:05] [Server thread/INFO]: Steve was slain by Zombie\n")
        self.assertEqual(DeathLogWatcher(str(self.path), "").poll(), 0)

    def test_partial_line_waits_for_newline(self):
        self.write("[12:00:05] [Server thread/INFO]: Steve was sla")
        watcher = DeathLogWatcher(str(self.path), "Steve")
        self.assertEqual(watcher.poll(), 0)
        self.write("in by Zombie\n", mode="a")
        self.assertEqual(watcher.poll(), 1)

    def test_new_log_file_is_read_from_start(self):
        self.write("[12:00:05] [Server thread/INFO]: Steve was slain by Zombie\n" * 1 + "x" * 200 + "\n")
        watcher = DeathLogWatcher(str(self.path), "Steve")
        self.assertEqual(watcher.poll(), 1)
        # เกมเปิดใหม่ -> ไฟล์เล็กลง
        self.write("[13:00:00] [Server thread/INFO]: Steve drowned\n")
        self.assertEqual(watcher.poll(), 1)

    def test_seek_end_skips_old_deaths(self):
        self.write("[12:00:05] [Server thread/INFO]: Steve was slain by Zombie\n")
        watcher = DeathLogWatcher(str(self.path), "Steve")
        watcher.seek_end()
        self.assertEqual(watcher.poll(), 0)
        self.write("[12:10:00] [Server thread/INFO]: Steve burned to death\n", mode="a")
        self.assertEqual(watcher.poll(), 1)

    def test_missing_file_is_fine(self):
        watcher = DeathLogWatcher(str(self.path), "Steve")
        watcher.seek_end()
        self.assertEqual(watcher.poll(), 0)


if __name__ == "__main__":
    unittest.main()
