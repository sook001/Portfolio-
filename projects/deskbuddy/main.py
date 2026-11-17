"""จุดเริ่มต้นของ DeskBuddy:  python main.py   (หรือ pythonw main.py เพื่อไม่ให้มีหน้าต่างดำ)"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):  # ถ้าแพ็กเป็น .exe ให้เก็บไฟล์ตั้งค่าไว้ข้าง ๆ ตัว .exe
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(BASE_DIR))

from deskbuddy.app import run  # noqa: E402

if __name__ == "__main__":
    run(BASE_DIR)
