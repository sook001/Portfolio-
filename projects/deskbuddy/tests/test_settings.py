"""ทดสอบหน้าตั้งค่า

ส่วนตรรกะรันได้ทุกเครื่อง ส่วนหน้าต่างจริง (tkinter) จะข้ามอัตโนมัติถ้าเครื่องไม่มี tkinter/หน้าจอ
รัน:  python -m unittest discover -s tests -v
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from deskbuddy import settings_model as sm  # noqa: E402
from deskbuddy.config import DEFAULTS, load_config, save_config  # noqa: E402
from deskbuddy.games import GameDef, load_games, save_games  # noqa: E402
from test_deskbuddy import advance, greet, make_engine  # noqa: E402

try:
    import tkinter as tk

    _probe = tk.Tk()
    _probe.destroy()
    HAVE_TK = True
except Exception:  # ไม่มี tkinter หรือไม่มีหน้าจอ
    HAVE_TK = False


class ParseTests(unittest.TestCase):
    def test_parse_time(self):
        self.assertEqual(sm.parse_time("7:30"), "07:30")
        self.assertEqual(sm.parse_time(" 07.30 "), "07:30")
        self.assertEqual(sm.parse_time("23:59"), "23:59")
        for bad in ("", "abc", "24:00", "12:60", "12", "12:5", "-1:30"):
            with self.assertRaises(ValueError, msg=bad):
                sm.parse_time(bad)

    def test_parse_time_range_names_the_field(self):
        with self.assertRaises(ValueError) as ctx:
            sm.parse_time_range("มื้อเที่ยง", "12:00", "xx")
        self.assertIn("มื้อเที่ยง", str(ctx.exception))
        with self.assertRaises(ValueError):
            sm.parse_time_range("มื้อเที่ยง", "12:00", "12:00")
        self.assertEqual(sm.parse_time_range("นอน", "23:00", "05:00"), ("23:00", "05:00"))  # ข้ามเที่ยงคืนได้

    def test_parse_processes(self):
        self.assertEqual(sm.parse_processes("cs2.exe, Dota2.EXE ,\"x y.exe\""), ["cs2.exe", "Dota2.EXE", "x y.exe"])
        self.assertEqual(sm.parse_processes("javaw"), ["javaw.exe"])  # ลืม .exe
        self.assertEqual(sm.parse_processes("a.exe, A.exe, ,"), ["a.exe"])  # ตัดซ้ำ ตัดว่าง
        self.assertEqual(sm.parse_processes(""), [])

    def test_validate_game_fields(self):
        self.assertEqual(sm.validate_game_fields(" My Game ", "g", "  ", []), ("My Game", ["g.exe"], None))
        self.assertEqual(sm.validate_game_fields("J", "javaw.exe", "Minecraft", [])[2], "Minecraft")
        with self.assertRaises(ValueError):
            sm.validate_game_fields("", "g.exe", "", [])
        with self.assertRaises(ValueError):
            sm.validate_game_fields("X", "", "", [])
        with self.assertRaises(ValueError):
            sm.validate_game_fields("minecraft", "g.exe", "", ["Minecraft"])  # ชื่อซ้ำ ไม่สนตัวพิมพ์


class BuildConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(DEFAULTS)
        self.cfg["break_after_minutes"] = 90  # ค่าที่หน้าตั้งค่าไม่ได้แก้ ต้องไม่หาย
        self.meals = {k: (True, *v) for k, v in self.cfg["meals"].items()}
        self.night = (True, "01:00", "05:00")

    def test_updates_only_form_fields(self):
        meals = dict(self.meals, lunch=(False, "12:00", "14:00"))
        new = sm.build_config(self.cfg, user_name="  สุข ", personality="teasing", meals=meals, night=(False, "0:30", "4:00"))
        self.assertEqual(new["user_name"], "สุข")
        self.assertEqual(new["personality"], "teasing")
        self.assertEqual(new["meals"]["lunch"], ["12:00", "14:00"])
        self.assertFalse(new["meals_enabled"]["lunch"])
        self.assertTrue(new["meals_enabled"]["dinner"])
        self.assertEqual(new["late_night"], dict(self.cfg["late_night"], enabled=False, start="00:30", end="04:00"))
        self.assertEqual(new["break_after_minutes"], 90)
        self.assertEqual(self.cfg["meals"]["lunch"], DEFAULTS["meals"]["lunch"])  # ต้นฉบับไม่ถูกแก้

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            sm.build_config(self.cfg, user_name="", personality="", meals=self.meals, night=self.night)
        with self.assertRaises(ValueError):
            sm.build_config(self.cfg, user_name="", personality="friendly",
                            meals=dict(self.meals, dinner=(True, "18:00", "25:00")), night=self.night)
        with self.assertRaises(ValueError):
            sm.build_config(self.cfg, user_name="", personality="friendly",
                            meals=self.meals, night=(True, "03:00", "03:00"))


class FileTests(unittest.TestCase):
    def test_list_personalities(self):
        found = dict(sm.list_personalities(ROOT / "personalities"))
        self.assertEqual(found.get("friendly"), "เพื่อนสนิทใจดี")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "broken.json").write_text("{nope")
            (Path(tmp) / "notpersonality.json").write_text('{"hello": 1}')
            self.assertEqual(sm.list_personalities(Path(tmp)), [])

    def test_games_roundtrip_keeps_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.json"
            games = load_games(ROOT / "games.json")
            games.append(GameDef("Two Exes", ["a.exe", "b.exe"]))
            save_games(path, games)
            again = load_games(path)
            self.assertEqual([g.name for g in again], [g.name for g in games])
            mc = next(g for g in again if g.name == "Minecraft")
            self.assertEqual(mc.window_contains, "Minecraft")
            self.assertIn("death_log", json.loads(path.read_text(encoding="utf-8"))[0])
            two = next(g for g in again if g.name == "Two Exes")
            self.assertEqual(two.processes, ["a.exe", "b.exe"])

    def test_save_config_roundtrip_and_no_temp_files_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = copy.deepcopy(DEFAULTS)
            cfg["user_name"] = "สุข"
            save_config(path, cfg)
            self.assertEqual(load_config(path)["user_name"], "สุข")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["config.json"])


class MealEnabledTests(unittest.TestCase):
    def test_disabled_meal_is_never_asked(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = make_engine(tmp, start, meals_enabled={"lunch": False})
            t = greet(engine, start)
            t, found = advance(engine, t, 90 * 60, idle=30.0)
            self.assertEqual(found, [])

    def test_missing_flag_defaults_to_enabled(self):
        start = datetime(2026, 11, 10, 11, 59, 50)
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = make_engine(tmp, start)
            del engine.cfg["meals_enabled"]  # config เก่าที่ยังไม่มีคีย์นี้
            t = greet(engine, start)
            t, found = advance(engine, t, 25 * 60, idle=30.0)
            self.assertEqual(found[0][1].kind, "meal")


@unittest.skipUnless(HAVE_TK, "ไม่มี tkinter/หน้าจอ ข้ามการทดสอบหน้าต่างจริง")
class SettingsWindowTests(unittest.TestCase):
    def setUp(self):
        from deskbuddy.settings_window import SettingsWindow

        self.SettingsWindow = SettingsWindow
        self.root = tk.Tk()
        self.root.withdraw()
        self.cfg = copy.deepcopy(DEFAULTS)
        self.games = load_games(ROOT / "games.json")
        self.saved = []

        def on_save(cfg, games, auto):
            self.saved.append((cfg, games, auto))
            return []

        self.on_save = on_save
        self.win = SettingsWindow(
            self.root, self.cfg, self.games, sm.list_personalities(ROOT / "personalities"), False, on_save
        )
        self.root.update()
        patcher = mock.patch("deskbuddy.settings_window.messagebox")
        self.mb = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.win.close()
        self.root.destroy()

    def test_opens_with_current_values(self):
        self.assertEqual(self.win.v_name.get(), "")
        self.assertEqual(self.win.v_personality.get(), "เพื่อนสนิทใจดี")
        self.assertEqual(self.win.meal_vars["lunch"][1].get(), "11:30")
        self.assertEqual(self.win.listbox.size(), len(self.games))
        self.assertEqual(self.win.v_gname.get(), self.games[0].name)

    def test_save_general_and_meals(self):
        self.win.v_name.set("สุข")
        self.win.v_auto.set(True)
        on, s, e = self.win.meal_vars["lunch"]
        on.set(False)
        s.set("12:15")
        self.win.v_night_on.set(False)
        self.win.save()
        self.assertEqual(len(self.saved), 1)
        cfg, games, auto = self.saved[0]
        self.assertEqual(cfg["user_name"], "สุข")
        self.assertEqual(cfg["personality"], "friendly")
        self.assertEqual(cfg["meals"]["lunch"][0], "12:15")
        self.assertFalse(cfg["meals_enabled"]["lunch"])
        self.assertFalse(cfg["late_night"]["enabled"])
        self.assertTrue(auto)
        self.assertEqual([g.name for g in games], [g.name for g in self.games])
        self.mb.showerror.assert_not_called()

    def test_bad_time_blocks_save(self):
        self.win.meal_vars["dinner"][1].set("99:99")
        self.win.save()
        self.assertEqual(self.saved, [])
        self.mb.showerror.assert_called_once()
        self.assertIn("มื้อเย็น", self.mb.showerror.call_args[0][1])

    def test_add_edit_and_delete_game(self):
        before = len(self.games)
        self.win._add_game()
        self.assertEqual(self.win.listbox.size(), before + 1)
        self.assertEqual(self.win.v_gname.get(), "เกมใหม่")
        self.win.v_gname.set("Terraria")
        self.win.v_procs.set("Terraria")
        self.win.save()
        cfg, games, _ = self.saved[-1]
        added = next(g for g in games if g.name == "Terraria")
        self.assertEqual(added.processes, ["Terraria.exe"])
        self.assertIsNone(added.death_log)
        self.assertEqual(self.win.listbox.get(before), "Terraria")

        self.mb.askyesno.return_value = True
        self.win._delete_game()
        self.win.save()
        _, games, _ = self.saved[-1]
        self.assertNotIn("Terraria", [g.name for g in games])
        self.assertEqual(len(games), before)

    def test_new_game_without_process_blocks_switching_and_saving(self):
        self.win._add_game()
        new_index = self.win.current
        self.win.listbox.selection_clear(0, "end")
        self.win.listbox.selection_set(0)
        self.win._on_select()  # พยายามกดเลือกเกมอื่นทั้งที่ฟอร์มยังไม่ครบ
        self.assertEqual(self.win.current, new_index)
        self.mb.showerror.assert_called()
        self.win.save()
        self.assertEqual(self.saved, [])

    def test_player_field_only_for_games_with_death_log(self):
        names = [g.name for g in self.games]
        mc = names.index("Minecraft")
        self.win.listbox.selection_clear(0, "end")
        self.win.listbox.selection_set(mc)
        self.win._on_select()
        self.assertNotIn("disabled", self.win.e_player.state())
        self.win.v_player.set("Steve")
        other = next(i for i, n in enumerate(names) if n != "Minecraft")
        self.win.listbox.selection_clear(0, "end")
        self.win.listbox.selection_set(other)
        self.win._on_select()
        self.assertIn("disabled", self.win.e_player.state())
        self.win.save()
        _, games, _ = self.saved[-1]
        self.assertEqual(next(g for g in games if g.name == "Minecraft").death_log["player"], "Steve")

    def test_duplicate_game_name_rejected(self):
        self.win._add_game()
        self.win.v_gname.set("minecraft")
        self.win.v_procs.set("x.exe")
        self.win.save()
        self.assertEqual(self.saved, [])
        self.assertIn("มีเกมชื่อ", self.mb.showerror.call_args[0][1])

    def test_on_save_failure_is_reported_not_raised(self):
        self.win.on_save = mock.Mock(side_effect=OSError("disk full"))
        self.win.save()
        self.mb.showerror.assert_called_once()
        self.assertIn("disk full", self.mb.showerror.call_args[0][1])
        self.assertEqual(self.win.status.cget("text"), "")


@unittest.skipUnless(HAVE_TK, "ไม่มี tkinter/หน้าจอ ข้ามการทดสอบแอปจริง")
class AppApplySettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = Path(self.tmp) / "app"
        self.base.mkdir()
        shutil.copytree(ROOT / "personalities", self.base / "personalities")
        shutil.copy(ROOT / "games.json", self.base / "games.json")
        (self.base / "personalities" / "teasing.json").write_text(
            (ROOT / "personalities" / "friendly.json").read_text(encoding="utf-8").replace("เพื่อนสนิทใจดี", "ขี้แซว"),
            encoding="utf-8",
        )
        from deskbuddy import app as appmod

        self.appmod = appmod
        self.app = appmod.App(self.base)
        self.addCleanup(self.app.root.destroy)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_apply_writes_files_and_takes_effect_immediately(self):
        app = self.app
        new_cfg = copy.deepcopy(app.cfg)
        new_cfg["user_name"] = "สุข"
        new_cfg["personality"] = "teasing"
        new_cfg["meals_enabled"]["lunch"] = False
        games = load_games(self.base / "games.json")
        games[0].death_log["player"] = "Steve"
        with mock.patch.object(self.appmod.autostart, "is_enabled", return_value=False), \
                mock.patch.object(self.appmod.autostart, "enable", return_value=True) as enable:
            warnings = app.apply_settings(new_cfg, games, True)
        self.assertEqual(warnings, [])
        enable.assert_called_once()
        # ไฟล์บนดิสก์
        self.assertEqual(json.loads((self.base / "config.json").read_text(encoding="utf-8"))["user_name"], "สุข")
        self.assertEqual(load_games(self.base / "games.json")[0].death_log["player"], "Steve")
        # ค่าที่ engine เห็น (ใช้ dict ตัวเดียวกัน)
        self.assertIs(app.engine.cfg, app.cfg)
        self.assertFalse(app.engine.cfg["meals_enabled"]["lunch"])
        self.assertEqual(app.engine.msg.user_name, "สุข")
        self.assertEqual(app.engine.msg.name, "ขี้แซว")
        self.assertIn("Minecraft", app.watchers)

    def test_autostart_failure_becomes_warning(self):
        app = self.app
        with mock.patch.object(self.appmod.autostart, "is_enabled", return_value=False), \
                mock.patch.object(self.appmod.autostart, "enable", return_value=False):
            warnings = app.apply_settings(copy.deepcopy(app.cfg), app.games, True)
        self.assertEqual(len(warnings), 1)

    def test_missing_personality_file_saves_nothing(self):
        app = self.app
        new_cfg = copy.deepcopy(app.cfg)
        new_cfg["personality"] = "does_not_exist"
        before = (self.base / "games.json").read_text(encoding="utf-8")
        with self.assertRaises(OSError):
            app.apply_settings(new_cfg, app.games, False)
        self.assertFalse((self.base / "config.json").exists() and
                         json.loads((self.base / "config.json").read_text(encoding="utf-8")).get("personality") == "does_not_exist")
        self.assertEqual((self.base / "games.json").read_text(encoding="utf-8"), before)
        self.assertNotEqual(app.cfg["personality"], "does_not_exist")

    def test_watcher_kept_when_unchanged_and_skips_old_log_when_new(self):
        app = self.app
        games = load_games(self.base / "games.json")
        games[0].death_log["player"] = "Steve"
        games[0].death_log["path"] = str(self.base / "latest.log")
        (self.base / "latest.log").write_text("[12:00:00] [Server thread/INFO]: Steve drowned\n", encoding="utf-8")
        app._prev_running = {"Minecraft"}  # เกมกำลังรันอยู่ตอนตั้งค่า
        with mock.patch.object(self.appmod.autostart, "is_enabled", return_value=False):
            app.apply_settings(copy.deepcopy(app.cfg), games, False)
            watcher = app.watchers["Minecraft"]
            self.assertEqual(watcher.poll(), 0)  # ข้ามการตายเก่าในไฟล์
            app.apply_settings(copy.deepcopy(app.cfg), games, False)
            self.assertIs(app.watchers["Minecraft"], watcher)  # ไม่เปลี่ยน -> ใช้ตัวเดิม


class PreviewEngineTests(unittest.TestCase):
    """ปุ่มทดสอบต้องไม่ไปนับ/บันทึก/ขยับเวลาเตือนจริง"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.t0 = datetime(2026, 11, 10, 10, 0, 0)
        self.engine, self.stats = make_engine(self.tmpdir.name, self.t0, user_name="สุข")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_scenario_lists_match(self):
        from deskbuddy.engine import PREVIEW_SCENARIOS

        in_model = [sid for _, items in sm.PREVIEW_GROUPS for sid, _ in items]
        self.assertEqual(sorted(in_model), sorted(PREVIEW_SCENARIOS))
        self.assertEqual(len(in_model), len(set(in_model)))

    def test_every_scenario_builds_a_clean_request(self):
        for _, items in sm.PREVIEW_GROUPS:
            for sid, _label in items:
                request = self.engine.preview(sid)
                self.assertTrue(request.text, sid)
                self.assertNotIn("{", request.text, sid)
                self.assertTrue(request.buttons, sid)
                self.assertTrue(request.context.get("preview"), sid)
                self.assertIn(request.kind, ("greeting", "meal", "break", "death", "night"), sid)

    def test_kinds_and_buttons_match_real_popups(self):
        e = self.engine
        self.assertEqual(e.preview("meal_lunch").kind, "meal")
        self.assertEqual([c for _, c in e.preview("meal_lunch").buttons], ["ate", "not_yet", "snooze"])
        self.assertEqual([c for _, c in e.preview("break").buttons], ["rest", "continue"])
        self.assertEqual([c for _, c in e.preview("death").buttons], ["rest", "continue"])
        self.assertEqual([c for _, c in e.preview("night").buttons], ["sleep", "later"])
        self.assertEqual([c for _, c in e.preview("greeting_day").buttons], ["ok"])

    def test_texts_use_config_values(self):
        self.engine.cfg["break_after_minutes"] = 180
        self.engine.cfg["death_streak"]["count"] = 7
        self.assertIn("3 ชั่วโมง", self.engine.preview("break").text)
        self.assertIn("Minecraft", self.engine.preview("break").text)
        self.assertIn("7", self.engine.preview("death").text)

    def test_meal_button_label_follows_snooze_setting_for_real_and_preview(self):
        self.engine.cfg["meal_snooze_minutes"] = 45
        self.assertEqual(self.engine.preview("meal_dinner").buttons[2][0], "เตือนอีก 45 นาที")
        start = datetime(2026, 11, 10, 11, 59, 50)
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = make_engine(tmp, start, meal_snooze_minutes=45)
            t = greet(engine, start)
            t, found = advance(engine, t, 25 * 60, idle=30.0)
            self.assertEqual(found[0][1].buttons[2][0], "เตือนอีก 45 นาที")

    def test_preview_changes_nothing(self):
        before = json.dumps(self.stats.data, sort_keys=True)
        engine = self.engine
        for _, items in sm.PREVIEW_GROUPS:
            for sid, _label in items:
                request = engine.preview(sid)
                for _text, choice in request.buttons + [("", "dismiss"), ("", "timeout")]:
                    engine.preview_reply(request, choice)
        self.assertEqual(json.dumps(self.stats.data, sort_keys=True), before)
        self.assertFalse(engine.popup_open)
        self.assertIsNone(engine.last_popup_at)
        self.assertFalse(engine.greeted)
        self.assertEqual(engine.sessions, {})

    def test_preview_does_not_block_real_popups(self):
        self.engine.preview("meal_lunch")
        t, found = advance(self.engine, self.t0, 30)  # ทักทายจริงต้องยังขึ้นตามปกติ
        self.assertEqual(found[0][1].kind, "greeting")

    def test_preview_reply_for_each_button(self):
        e = self.engine
        for sid in ("meal_lunch", "break", "death", "night"):
            request = e.preview(sid)
            for _text, choice in request.buttons:
                self.assertTrue(e.preview_reply(request, choice), (sid, choice))
        self.assertIsNone(e.preview_reply(e.preview("greeting_day"), "ok"))
        self.assertIsNone(e.preview_reply(e.preview("break"), "dismiss"))

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.preview("nope")


@unittest.skipUnless(HAVE_TK, "ไม่มี tkinter/หน้าจอ ข้ามการทดสอบหน้าต่างจริง")
class PreviewUiTests(unittest.TestCase):
    def setUp(self):
        from deskbuddy.settings_window import SettingsWindow

        self.root = tk.Tk()
        self.root.withdraw()
        self.calls = []
        self.win = SettingsWindow(
            self.root,
            copy.deepcopy(DEFAULTS),
            load_games(ROOT / "games.json"),
            sm.list_personalities(ROOT / "personalities"),
            False,
            lambda *a: [],
            on_preview=self.calls.append,
        )
        self.root.update()
        patcher = mock.patch("deskbuddy.settings_window.messagebox")
        self.mb = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.win.close()
        self.root.destroy()

    def test_every_button_calls_its_scenario(self):
        expected = [sid for _, items in sm.PREVIEW_GROUPS for sid, _ in items]
        self.assertEqual(sorted(self.win.preview_buttons), sorted(expected))
        for sid in expected:
            self.win.preview_buttons[sid].invoke()
        self.assertEqual(self.calls, expected)

    def test_error_is_shown_not_raised(self):
        self.win.on_preview = mock.Mock(side_effect=RuntimeError("boom"))
        self.win.preview_buttons["meal_lunch"].invoke()
        self.mb.showerror.assert_called_once()
        self.assertIn("boom", self.mb.showerror.call_args[0][1])

    def test_no_preview_tab_without_callback(self):
        from deskbuddy.settings_window import SettingsWindow

        win = SettingsWindow(self.root, copy.deepcopy(DEFAULTS), [], [("friendly", "x")], False, lambda *a: [])
        try:
            self.assertEqual(win.preview_buttons, {})
        finally:
            win.close()


@unittest.skipUnless(HAVE_TK, "ไม่มี tkinter/หน้าจอ ข้ามการทดสอบแอปจริง")
class AppPreviewTests(unittest.TestCase):
    def test_show_preview_uses_preview_reply_and_counts_nothing(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        base = Path(tmp) / "app"
        base.mkdir()
        shutil.copytree(ROOT / "personalities", base / "personalities")
        shutil.copy(ROOT / "games.json", base / "games.json")
        from deskbuddy import app as appmod

        app = appmod.App(base)
        self.addCleanup(app.root.destroy)
        with mock.patch.object(appmod, "Popup") as popup:
            app.show_preview("meal_lunch")
        popup.assert_called_once()
        _root, request, on_answer = popup.call_args[0]
        self.assertEqual(request.kind, "meal")
        reply = on_answer("ate")
        self.assertTrue(reply)
        self.assertEqual(app.stats.data["days"], {})  # ไม่นับป๊อปอัป ไม่บันทึกว่ากินแล้ว
        self.assertEqual(app.stats.data["slots"], {})
        self.assertFalse(app.engine.popup_open)

    def test_show_preview_creates_real_popup_window(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        base = Path(tmp) / "app"
        base.mkdir()
        shutil.copytree(ROOT / "personalities", base / "personalities")
        shutil.copy(ROOT / "games.json", base / "games.json")
        from deskbuddy import app as appmod

        app = appmod.App(base)
        self.addCleanup(app.root.destroy)
        app.show_preview("night")
        app.root.update()
        popups = [w for w in app.root.winfo_children() if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(popups), 1)
        popups[0].destroy()


if __name__ == "__main__":
    unittest.main()
