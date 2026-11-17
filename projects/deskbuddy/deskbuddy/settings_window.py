"""หน้าต่างตั้งค่า (tkinter + ttk) 3 แท็บ: ทั่วไป / มื้ออาหาร-นอน / เกม

ไม่แตะไฟล์เอง แค่เรียก on_save(new_cfg, games, autostart_on) ที่ App ส่งมา
"""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from . import settings_model as sm
from .games import GameDef

FONT = ("Tahoma", 10)
HINT = "#7a7f8f"
NEW_GAME_NAME = "เกมใหม่"


def _work_item(game: GameDef) -> dict:
    return {
        "name": game.name,
        "processes": list(game.processes),
        "window_contains": game.window_contains,
        "death_log": copy.deepcopy(game.death_log),
    }


class SettingsWindow:
    def __init__(
        self,
        root: tk.Misc,
        cfg: dict,
        games: list,
        personalities: list,
        autostart_enabled: bool,
        on_save: Callable[[dict, list, bool], list],
        on_preview: Callable[[str], None] | None = None,
    ):
        self.cfg = copy.deepcopy(cfg)
        self.on_save = on_save
        self.on_preview = on_preview
        self.preview_buttons: dict = {}
        self.work = [_work_item(g) for g in games]
        self.current: int | None = None

        top = self.top = tk.Toplevel(root)
        top.title("DeskBuddy — ตั้งค่า")
        top.minsize(560, 470)
        top.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(top)
        style.configure(".", font=FONT)
        style.configure("TNotebook.Tab", padding=(14, 6))
        style.configure("Hint.TLabel", foreground=HINT)

        body = ttk.Frame(top, padding=(12, 12, 12, 4))
        body.pack(fill="both", expand=True)
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True)
        notebook.add(self._build_general(notebook, personalities, autostart_enabled), text="ทั่วไป")
        notebook.add(self._build_meals(notebook), text="มื้ออาหาร / นอน")
        notebook.add(self._build_games(notebook), text="เกม")
        if self.on_preview is not None:
            notebook.add(self._build_preview(notebook), text="ทดสอบ")

        bar = ttk.Frame(top, padding=(12, 6, 12, 12))
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(bar, text="ปิด", command=self.close).pack(side="right")
        ttk.Button(bar, text="บันทึก", command=self.save).pack(side="right", padx=(0, 8))

        self._refresh_list(select=0 if self.work else None)
        top.lift()
        top.focus_force()

    # ------------------------------------------------------------------
    # สถานะหน้าต่าง
    # ------------------------------------------------------------------
    def exists(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def focus(self) -> None:
        if self.exists():
            self.top.deiconify()
            self.top.lift()
            self.top.focus_force()

    def close(self) -> None:
        if self.exists():
            self.top.destroy()

    # ------------------------------------------------------------------
    # แท็บทั่วไป
    # ------------------------------------------------------------------
    def _build_general(self, parent, personalities: list, autostart_enabled: bool) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=18)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="ชื่อที่ให้เพื่อนเรียก").grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.v_name = tk.StringVar(value=self.cfg.get("user_name", ""))
        ttk.Entry(frame, textvariable=self.v_name, width=30).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(frame, text="เว้นว่างได้ ถ้าว่างเพื่อนจะไม่เรียกชื่อ", style="Hint.TLabel").grid(
            row=1, column=1, sticky="w", padx=(12, 0), pady=(0, 14)
        )

        # บุคลิก: แสดงชื่อที่อ่านง่าย ถ้าชื่อซ้ำกันจะต่อท้ายด้วยชื่อไฟล์
        current_stem = self.cfg.get("personality", "")
        stems = [s for s, _ in personalities]
        if current_stem and current_stem not in stems:
            personalities = personalities + [(current_stem, current_stem)]
        names = [n for _, n in personalities]
        self.label_to_stem: dict = {}
        labels = []
        for stem, name in personalities:
            label = f"{name} [{stem}]" if names.count(name) > 1 else name
            self.label_to_stem[label] = stem
            labels.append(label)
        ttk.Label(frame, text="บุคลิกของเพื่อน").grid(row=2, column=0, sticky="w", pady=(0, 2))
        self.v_personality = tk.StringVar()
        for label, stem in self.label_to_stem.items():
            if stem == current_stem:
                self.v_personality.set(label)
        ttk.Combobox(
            frame, textvariable=self.v_personality, values=labels, state="readonly", width=28
        ).grid(row=2, column=1, sticky="w", padx=(12, 0))
        ttk.Label(
            frame, text="เพิ่มบุคลิกใหม่ได้โดยคัดลอกไฟล์ในโฟลเดอร์ personalities", style="Hint.TLabel"
        ).grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(0, 14))

        self.v_auto = tk.BooleanVar(value=autostart_enabled)
        ttk.Checkbutton(frame, text="เปิดโปรแกรมพร้อม Windows", variable=self.v_auto).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 14)
        )

        ttk.Label(
            frame,
            text="ค่าอื่น เช่น เล่นนานกี่ชั่วโมงถึงทัก หรือจำนวนครั้งสูงสุดต่อวัน แก้ได้ที่ไฟล์ config.json",
            style="Hint.TLabel",
            wraplength=460,
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w")
        return frame

    # ------------------------------------------------------------------
    # แท็บมื้ออาหาร / นอน
    # ------------------------------------------------------------------
    def _build_meals(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=18)
        ttk.Label(frame, text="ช่วงเวลาที่เพื่อนจะถามเรื่องกินข้าว", font=(FONT[0], 10, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w", pady=(0, 8)
        )
        enabled_map = self.cfg.get("meals_enabled", {})
        self.meal_vars: dict = {}
        for row, (key, label) in enumerate(sm.MEAL_LABELS.items(), start=1):
            start, end = self.cfg["meals"][key]
            on = tk.BooleanVar(value=bool(enabled_map.get(key, True)))
            v_start, v_end = tk.StringVar(value=start), tk.StringVar(value=end)
            self.meal_vars[key] = (on, v_start, v_end)
            ttk.Checkbutton(frame, text=label, variable=on, width=10).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(frame, textvariable=v_start, width=7, justify="center").grid(row=row, column=1, padx=(8, 0))
            ttk.Label(frame, text="ถึง").grid(row=row, column=2, padx=8)
            ttk.Entry(frame, textvariable=v_end, width=7, justify="center").grid(row=row, column=3)

        ttk.Separator(frame).grid(row=4, column=0, columnspan=5, sticky="ew", pady=16)
        ttk.Label(frame, text="ช่วงเวลาที่เพื่อนจะทักเรื่องนอน", font=(FONT[0], 10, "bold")).grid(
            row=5, column=0, columnspan=5, sticky="w", pady=(0, 8)
        )
        late = self.cfg.get("late_night", {})
        self.v_night_on = tk.BooleanVar(value=bool(late.get("enabled", True)))
        self.v_night_start = tk.StringVar(value=late.get("start", "01:00"))
        self.v_night_end = tk.StringVar(value=late.get("end", "05:00"))
        ttk.Checkbutton(frame, text="เปิดใช้", variable=self.v_night_on, width=10).grid(row=6, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.v_night_start, width=7, justify="center").grid(row=6, column=1, padx=(8, 0))
        ttk.Label(frame, text="ถึง").grid(row=6, column=2, padx=8)
        ttk.Entry(frame, textvariable=self.v_night_end, width=7, justify="center").grid(row=6, column=3)

        ttk.Label(
            frame,
            text=(
                "ใส่เวลาแบบ 24 ชั่วโมง เช่น 12:30 ช่วงที่ข้ามเที่ยงคืนได้ เช่น 23:00 ถึง 05:00\n"
                "เพื่อนจะถามเรื่องกินข้าวเฉพาะตอนที่คุณไม่ได้เล่นเกมและไม่ได้ขยับเมาส์/คีย์บอร์ดชั่วครู่"
            ),
            style="Hint.TLabel",
            justify="left",
            wraplength=470,
        ).grid(row=7, column=0, columnspan=5, sticky="w", pady=(18, 0))
        return frame

    # ------------------------------------------------------------------
    # แท็บเกม
    # ------------------------------------------------------------------
    def _build_games(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        left = ttk.Frame(frame)
        left.pack(side="left", fill="y")
        self.listbox = tk.Listbox(left, width=22, height=13, exportselection=False, font=FONT, activestyle="none")
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="+ เพิ่มเกม", command=self._add_game).pack(side="left")
        ttk.Button(row, text="ลบ", command=self._delete_game, width=6).pack(side="right")

        right = ttk.Frame(frame, padding=(16, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        right.columnconfigure(0, weight=1)

        self.v_gname = tk.StringVar()
        self.v_procs = tk.StringVar()
        self.v_window = tk.StringVar()
        self.v_player = tk.StringVar()

        ttk.Label(right, text="ชื่อเกม (ที่ให้แสดง)").grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.v_gname).grid(row=1, column=0, sticky="ew", pady=(2, 10))

        ttk.Label(right, text="ชื่อ process (.exe) คั่นด้วย , ถ้ามีหลายตัว").grid(row=2, column=0, sticky="w")
        self.e_procs = ttk.Entry(right, textvariable=self.v_procs)
        self.e_procs.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(right, text="เลือกจากโปรแกรมที่กำลังรัน…", command=self._pick_process).grid(
            row=4, column=0, sticky="w", pady=(0, 10)
        )

        ttk.Label(right, text="ชื่อหน้าต่างต้องมีคำว่า (ไม่บังคับ)").grid(row=5, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.v_window).grid(row=6, column=0, sticky="ew", pady=(2, 0))
        ttk.Label(
            right,
            text="ใช้กับเกมที่รันผ่าน javaw.exe เพื่อไม่ให้ปนกับโปรแกรม Java อื่น",
            style="Hint.TLabel",
            wraplength=300,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(0, 10))

        ttk.Label(right, text="ชื่อตัวละคร (นับจำนวนครั้งที่ตาย)").grid(row=8, column=0, sticky="w")
        self.e_player = ttk.Entry(right, textvariable=self.v_player)
        self.e_player.grid(row=9, column=0, sticky="ew", pady=(2, 0))
        self.player_hint = ttk.Label(right, text="", style="Hint.TLabel", wraplength=300, justify="left")
        self.player_hint.grid(row=10, column=0, sticky="w")
        return frame

    def _names_except(self, index: int | None) -> list:
        return [w["name"] for i, w in enumerate(self.work) if i != index]

    def _refresh_list(self, select: int | None = None) -> None:
        self.listbox.delete(0, "end")
        for item in self.work:
            self.listbox.insert("end", item["name"])
        if select is not None and 0 <= select < len(self.work):
            self.listbox.selection_set(select)
            self.listbox.see(select)
            self.current = select
        else:
            self.current = None
        self._load_form()

    def _load_form(self) -> None:
        item = self.work[self.current] if self.current is not None else None
        self.v_gname.set(item["name"] if item else "")
        self.v_procs.set(", ".join(item["processes"]) if item else "")
        self.v_window.set((item["window_contains"] or "") if item else "")
        death_log = item["death_log"] if item else None
        self.v_player.set(str(death_log.get("player", "")) if death_log else "")
        if death_log is not None:
            self.e_player.state(["!disabled"])
            self.player_hint.config(text="ใช้ได้กับ Minecraft Java เท่านั้น (อ่านไฟล์ latest.log)")
        else:
            self.e_player.state(["disabled"])
            self.player_hint.config(text="เกมนี้ยังไม่รองรับการนับจำนวนครั้งที่ตาย")

    def _commit_form(self) -> bool:
        """เก็บค่าในฟอร์มกลับเข้ารายการ คืน False ถ้าค่าไม่ถูกต้อง (และแสดงข้อความแล้ว)"""
        if self.current is None:
            return True
        try:
            name, processes, window = sm.validate_game_fields(
                self.v_gname.get(), self.v_procs.get(), self.v_window.get(), self._names_except(self.current)
            )
        except ValueError as exc:
            messagebox.showerror("ข้อมูลเกมไม่ถูกต้อง", str(exc), parent=self.top)
            return False
        item = self.work[self.current]
        item["name"], item["processes"], item["window_contains"] = name, processes, window
        if item["death_log"] is not None:
            item["death_log"]["player"] = self.v_player.get().strip()
        index = self.current
        self.listbox.delete(index)
        self.listbox.insert(index, name)
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        return True

    def _on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection or selection[0] == self.current:
            return
        new_index = selection[0]
        if not self._commit_form():
            self.listbox.selection_clear(0, "end")
            if self.current is not None:
                self.listbox.selection_set(self.current)
            return
        self.current = new_index
        self._load_form()

    def _add_game(self) -> None:
        if not self._commit_form():
            return
        existing = {n.lower() for n in self._names_except(None)}
        name, n = NEW_GAME_NAME, 1
        while name.lower() in existing:
            n += 1
            name = f"{NEW_GAME_NAME} {n}"
        self.work.append({"name": name, "processes": [], "window_contains": None, "death_log": None})
        self._refresh_list(select=len(self.work) - 1)

    def _delete_game(self) -> None:
        if self.current is None:
            return
        name = self.work[self.current]["name"]
        if not messagebox.askyesno("ลบเกม", f"ลบ '{name}' ออกจากรายการใช่ไหม\n(สถิติที่เคยบันทึกไว้ไม่หาย)", parent=self.top):
            return
        index = self.current
        del self.work[index]
        self._refresh_list(select=min(index, len(self.work) - 1) if self.work else None)

    def _pick_process(self) -> None:
        if self.current is None:
            messagebox.showinfo("เลือกโปรแกรม", "เลือกเกมในรายการ หรือกด + เพิ่มเกม ก่อนครับ", parent=self.top)
            return
        try:
            import psutil

            names = sorted(
                {p.info["name"] for p in psutil.process_iter(["name"]) if p.info.get("name")},
                key=str.lower,
            )
        except Exception:
            names = []

        dlg = tk.Toplevel(self.top)
        dlg.title("เลือกโปรแกรมที่กำลังรัน")
        dlg.transient(self.top)
        dlg.geometry("360x420")
        ttk.Label(
            dlg,
            text="เปิดเกมค้างไว้ก่อน แล้วหาชื่อในรายการนี้\nดับเบิลคลิกเพื่อเพิ่มลงช่องชื่อ process",
            padding=10,
            justify="left",
        ).pack(anchor="w")
        v_filter = tk.StringVar()
        ttk.Entry(dlg, textvariable=v_filter).pack(fill="x", padx=10)
        holder = ttk.Frame(dlg, padding=10)
        holder.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(holder)
        scroll.pack(side="right", fill="y")
        box = tk.Listbox(holder, font=FONT, yscrollcommand=scroll.set, activestyle="none")
        box.pack(side="left", fill="both", expand=True)
        scroll.config(command=box.yview)

        def refill(*_):
            needle = v_filter.get().strip().lower()
            box.delete(0, "end")
            for name in names:
                if needle in name.lower():
                    box.insert("end", name)

        def choose(_event=None):
            sel = box.curselection()
            if not sel:
                return
            chosen = box.get(sel[0])
            current = sm.parse_processes(self.v_procs.get())
            if chosen.lower() not in {c.lower() for c in current}:
                current.append(chosen)
            self.v_procs.set(", ".join(current))
            dlg.destroy()

        v_filter.trace_add("write", refill)
        box.bind("<Double-Button-1>", choose)
        refill()

    # ------------------------------------------------------------------
    # แท็บทดสอบ
    # ------------------------------------------------------------------
    def _build_preview(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        ttk.Label(
            frame,
            text=(
                "กดปุ่มเพื่อดูป๊อปอัปที่จะขึ้นจริง ลองกดปุ่มตอบดูได้ด้วย\n"
                "การทดสอบไม่นับเป็นข้อความของวัน ไม่บันทึกคำตอบ และไม่กระทบเวลาเตือนจริง\n"
                "ใช้ชื่อและบุคลิกที่บันทึกไว้แล้ว ถ้าเพิ่งแก้ ให้กด \"บันทึก\" ก่อน"
            ),
            style="Hint.TLabel",
            justify="left",
            wraplength=500,
        ).pack(anchor="w")
        for title, items in sm.PREVIEW_GROUPS:
            box = ttk.LabelFrame(frame, text=title, padding=(10, 6))
            box.pack(fill="x", pady=(10, 0))
            for i, (scenario, label) in enumerate(items):
                button = ttk.Button(box, text=label, command=lambda s=scenario: self._preview(s))
                button.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 8), pady=2)
                self.preview_buttons[scenario] = button
        return frame

    def _preview(self, scenario: str) -> None:
        try:
            self.on_preview(scenario)
        except Exception as exc:
            messagebox.showerror("แสดงตัวอย่างไม่สำเร็จ", str(exc), parent=self.top)

    # ------------------------------------------------------------------
    # บันทึก
    # ------------------------------------------------------------------
    def save(self) -> None:
        if not self._commit_form():
            return
        try:
            new_cfg = sm.build_config(
                self.cfg,
                user_name=self.v_name.get(),
                personality=self.label_to_stem.get(self.v_personality.get(), ""),
                meals={key: (on.get(), s.get(), e.get()) for key, (on, s, e) in self.meal_vars.items()},
                night=(self.v_night_on.get(), self.v_night_start.get(), self.v_night_end.get()),
            )
            games = []
            for item in self.work:
                # ตรวจซ้ำทุกเกม (กันเกมที่เพิ่มแล้วยังไม่ได้กรอก process)
                sm.validate_game_fields(
                    item["name"],
                    ", ".join(item["processes"]),
                    item["window_contains"] or "",
                    [w["name"] for w in self.work if w is not item],
                )
                games.append(
                    GameDef(
                        name=item["name"],
                        processes=item["processes"],
                        window_contains=item["window_contains"],
                        death_log=copy.deepcopy(item["death_log"]),
                    )
                )
        except ValueError as exc:
            messagebox.showerror("ข้อมูลไม่ถูกต้อง", str(exc), parent=self.top)
            return
        try:
            warnings = self.on_save(new_cfg, games, bool(self.v_auto.get())) or []
        except Exception as exc:
            messagebox.showerror("บันทึกไม่สำเร็จ", str(exc), parent=self.top)
            return
        self.cfg = new_cfg
        self.status.config(text="บันทึกแล้ว ใช้งานทันที ✓")
        self.top.after(4000, self._clear_status)
        for text in warnings:
            messagebox.showwarning("แจ้งเตือน", text, parent=self.top)

    def _clear_status(self) -> None:
        if self.exists():
            self.status.config(text="")
