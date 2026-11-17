"""รายชื่อเกมและการตรวจว่าเกมไหนกำลังรันอยู่"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


@dataclass
class GameDef:
    name: str
    processes: list = field(default_factory=list)  # ชื่อ process (.exe) เปรียบเทียบแบบไม่สนตัวพิมพ์
    window_contains: str | None = None  # ถ้าระบุ ต้องมีหน้าต่างที่ชื่อมีข้อความนี้ด้วย (ใช้กับ javaw.exe)
    death_log: dict | None = None  # {"path": ..., "player": ...}


def load_games(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("games.json ต้องเป็นรายการ (list) ของเกม")
    games = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError(f"games.json รายการที่ {i + 1} ต้องมี 'name'")
        procs = item.get("processes") or ([item["process"]] if item.get("process") else [])
        if not procs:
            raise ValueError(f"เกม '{item['name']}' ต้องมี 'process' หรือ 'processes'")
        games.append(
            GameDef(
                name=item["name"],
                processes=[str(p).lower() for p in procs],
                window_contains=item.get("window_contains"),
                death_log=item.get("death_log"),
            )
        )
    return games


def game_to_dict(game: GameDef) -> dict:
    out: dict = {"name": game.name}
    if len(game.processes) == 1:
        out["process"] = game.processes[0]
    else:
        out["processes"] = list(game.processes)
    if game.window_contains:
        out["window_contains"] = game.window_contains
    if game.death_log is not None:
        out["death_log"] = dict(game.death_log)
    return out


def save_games(path: Path, games: Iterable[GameDef]) -> None:
    from .config import write_json_atomic

    write_json_atomic(path, [game_to_dict(g) for g in games])


def detect(
    games: Iterable[GameDef],
    procs: Iterable[tuple],
    window_titles: Callable[[set], dict],
) -> set:
    """คืนชื่อเกมที่กำลังรัน

    procs: [(pid, ชื่อ process), ...]
    window_titles: ฟังก์ชันรับ set ของ pid คืน {pid: [ชื่อหน้าต่าง, ...]}
    """
    by_name: dict = {}
    for pid, name in procs:
        by_name.setdefault((name or "").lower(), []).append(pid)

    running = set()
    for game in games:
        pids = [pid for proc in game.processes for pid in by_name.get(proc, [])]
        if not pids:
            continue
        if game.window_contains:
            titles = window_titles(set(pids))
            needle = game.window_contains.lower()
            if not any(needle in t.lower() for ts in titles.values() for t in ts):
                continue
        running.add(game.name)
    return running
