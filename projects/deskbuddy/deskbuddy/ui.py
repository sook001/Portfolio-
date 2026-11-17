"""หน้าต่างป๊อปอัป (tkinter) และไอคอน system tray (pystray)"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .engine import PopupRequest

BG = "#232733"
FG = "#f4f1ea"
ACCENT = "#ff9f68"
BTN_BG = "#3a3f52"
BTN_ACTIVE = "#4a5068"
FONT = "Tahoma"  # มีอักษรไทยแน่นอนบน Windows


class Popup:
    """การ์ดเล็ก ๆ กลางจอ ไม่มีแถบชื่อ มีปุ่มตอบและปุ่ม × สำหรับปิด"""

    def __init__(
        self,
        root: tk.Tk,
        request: PopupRequest,
        on_answer: Callable[[str], Optional[str]],
        reply_seconds: float = 3.0,
    ):
        self.request = request
        self.on_answer = on_answer
        self.reply_ms = int(reply_seconds * 1000)
        self.done = False
        self._timer = None

        top = self.top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=ACCENT)  # เส้นขอบ

        inner = tk.Frame(top, bg=BG, padx=22, pady=14)
        inner.pack(padx=2, pady=2)

        header = tk.Frame(inner, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="DeskBuddy", bg=BG, fg=ACCENT, font=(FONT, 9, "bold")).pack(side="left")
        close = tk.Label(header, text="×", bg=BG, fg="#9aa0b4", font=(FONT, 14), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self._finish("dismiss"))

        self.text_label = tk.Label(
            inner,
            text=request.text,
            bg=BG,
            fg=FG,
            font=(FONT, 12),
            wraplength=340,
            justify="left",
            pady=10,
        )
        self.text_label.pack(anchor="w")

        self.button_row = tk.Frame(inner, bg=BG)
        self.button_row.pack(anchor="e", pady=(4, 0))
        for label, choice in request.buttons:
            tk.Button(
                self.button_row,
                text=label,
                command=lambda c=choice: self._finish(c),
                bg=BTN_BG,
                fg=FG,
                activebackground=BTN_ACTIVE,
                activeforeground=FG,
                relief="flat",
                font=(FONT, 10),
                padx=12,
                pady=4,
                cursor="hand2",
            ).pack(side="left", padx=(6, 0))

        self._center()
        if request.timeout_seconds:
            self._timer = top.after(int(request.timeout_seconds * 1000), lambda: self._finish("timeout"))

    def _center(self) -> None:
        self.top.update_idletasks()
        width, height = self.top.winfo_reqwidth(), self.top.winfo_reqheight()
        x = (self.top.winfo_screenwidth() - width) // 2
        y = (self.top.winfo_screenheight() - height) // 2
        self.top.geometry(f"+{x}+{y}")

    def _finish(self, choice: str) -> None:
        if self.done:
            return
        self.done = True
        if self._timer is not None:
            try:
                self.top.after_cancel(self._timer)
            except tk.TclError:
                pass
        try:
            reply = self.on_answer(choice)
        except Exception:
            reply = None
        if reply and choice not in ("dismiss", "timeout"):
            # โชว์คำตอบของเพื่อนสั้น ๆ แล้วค่อยปิด
            self.button_row.destroy()
            self.text_label.config(text=reply)
            self._center()
            self.top.after(self.reply_ms, self._destroy)
        else:
            self._destroy()

    def _destroy(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass


def make_tray_icon_image():
    """วาดไอคอนหน้ายิ้มเล็ก ๆ ด้วย Pillow ไม่ต้องมีไฟล์รูป"""
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, size - 2, size - 2), fill=(255, 159, 104, 255))
    draw.ellipse((19, 21, 27, 31), fill=(35, 39, 51, 255))
    draw.ellipse((37, 21, 45, 31), fill=(35, 39, 51, 255))
    draw.arc((18, 24, 46, 50), start=20, end=160, fill=(35, 39, 51, 255), width=3)
    return image
