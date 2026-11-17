"""เปิดโปรแกรมพร้อม Windows (ผู้ใช้ติ๊กเลือกเองจากเมนู tray เท่านั้น)

ใช้ Registry ของผู้ใช้ปัจจุบัน (HKCU ... \\Run) ไม่ต้องใช้สิทธิ์แอดมิน
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "DeskBuddy"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command(main_script: Path) -> str:
    if getattr(sys, "frozen", False):  # แพ็กเป็น .exe แล้ว
        return f'"{sys.executable}"'
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")  # ไม่เปิดหน้าต่างดำ
    runner = pythonw if pythonw.exists() else python
    return f'"{runner}" "{Path(main_script).resolve()}"'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable(main_script: Path) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command(main_script))
        return True
    except OSError:
        return False


def disable() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
