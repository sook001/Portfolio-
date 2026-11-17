"""ส่วนที่คุยกับ Windows โดยตรง (ใช้ ctypes ไม่ต้องลงไลบรารีเพิ่ม)

บนระบบที่ไม่ใช่ Windows ฟังก์ชันจะคืนค่าว่าง/ศูนย์ เพื่อให้ import และทดสอบได้
"""

from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
    _user32.GetLastInputInfo.restype = wintypes.BOOL
    _kernel32.GetTickCount.argtypes = []
    _kernel32.GetTickCount.restype = wintypes.DWORD

    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int

    _kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE

_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None  # เก็บไว้ไม่ให้ถูกเก็บกวาด


def idle_seconds() -> float:
    """กี่วินาทีแล้วที่ไม่มีการขยับเมาส์/พิมพ์คีย์บอร์ด

    ใช้ GetLastInputInfo ซึ่งบอกแค่เวลาของ input ล่าสุด ไม่เห็นว่ากดอะไร
    """
    if not IS_WINDOWS:
        return 0.0
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not _user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    elapsed_ms = (_kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


def window_titles(pids: set) -> dict:
    """{pid: [ชื่อหน้าต่างที่มองเห็นอยู่]} เฉพาะ pid ที่ขอ"""
    if not IS_WINDOWS:
        return {}
    result: dict = {}

    def callback(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            length = _user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                result.setdefault(pid.value, []).append(buf.value)
        return True

    _user32.EnumWindows(_EnumWindowsProc(callback), 0)
    return result


def acquire_single_instance(name: str = "DeskBuddy_SingleInstance") -> bool:
    """True = เราเป็นตัวแรก, False = มีโปรแกรมนี้เปิดอยู่แล้ว"""
    global _mutex_handle
    if not IS_WINDOWS:
        return True
    _mutex_handle = _kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


def enable_dpi_awareness() -> None:
    """กันตัวหนังสือในป๊อปอัปเบลอบนจอความละเอียดสูง"""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            _user32.SetProcessDPIAware()
        except Exception:
            pass
