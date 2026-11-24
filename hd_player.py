"""Display the HD frame matching the English ISO game's own movie counter."""

import ctypes as c
import hashlib
import struct
import sys
import time
from ctypes import wintypes as w
from pathlib import Path

import cv2
import psutil

u, k, g = c.windll.user32, c.windll.kernel32, c.windll.gdi32
u.SetProcessDPIAware()


def api(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = args, result
    return fn


ptr = c.c_void_p
create = api(
    u,
    "CreateWindowExW",
    ptr,
    w.DWORD,
    w.LPCWSTR,
    w.LPCWSTR,
    w.DWORD,
    c.c_int,
    c.c_int,
    c.c_int,
    c.c_int,
    ptr,
    ptr,
    ptr,
    ptr,
)
dc_for = api(u, "GetDC", ptr, ptr)
draw = api(
    g, "StretchDIBits", c.c_int, ptr, *([c.c_int] * 8), ptr, ptr, w.UINT, w.DWORD
)
release = api(u, "ReleaseDC", c.c_int, ptr, ptr)
position = api(
    u, "SetWindowPos", w.BOOL, ptr, ptr, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT
)
foreground = api(u, "GetForegroundWindow", ptr)
hidden = api(u, "ShowWindow", w.BOOL, ptr, c.c_int)
window_pid = api(u, "GetWindowThreadProcessId", w.DWORD, ptr, c.POINTER(w.DWORD))
read = api(k, "ReadProcessMemory", w.BOOL, ptr, ptr, ptr, c.c_size_t, ptr)
open_read = api(k, "OpenProcess", ptr, w.DWORD, w.BOOL, w.DWORD)
MSG = w.MSG()


def pump():
    while u.PeekMessageW(c.byref(MSG), None, 0, 0, 1):
        u.TranslateMessage(c.byref(MSG))
        u.DispatchMessageW(c.byref(MSG))


def log(msg):
    print(msg, flush=True)


def play(pid, base, runtime):
    process = psutil.Process(pid)
    identity = hashlib.sha256(Path(process.exe()).read_bytes()).hexdigest()
    if identity not in {
        "90cd971aff6570ae508d3011c6a0a84b9f61b433f3fef568bbf5854f14de9dd8",
        "de123bdb21262a2c0ff4f33c7fbc8d11ffde5c813bace83cfedf1e63f056f0b0",
    }:
        raise ValueError("Unsupported cinematic build")
    handle = open_read(0x10, False, pid)
    if not handle:
        raise c.WinError()
    # The standard STATIC class supplies a non-interactive display surface.
    window = create(
        0x080800A0,
        "STATIC",
        "Return Fire HD Cinematics",
        0x80000000,
        0,
        0,
        1,
        1,
        None,
        None,
        None,
        None,
    )
    if not window:
        raise c.WinError()
    u.SetLayeredWindowAttributes(window, 0, 255, 2)
    movies = runtime.parent / "HD-Cinematics"
    clips = {
        name
        for name in ("rf", "win", "win1", "win2", "win3")
        if (movies / (name + ".mp4")).is_file()
    }
    header = struct.pack(
        "<IiiHHIIiiII", 40, 1920, -1080, 1, 24, 0, 1920 * 1080 * 3, 0, 0, 0, 0
    )
    counter = c.c_uint32()
    cap = None
    clip = None
    last = -1
    next_probe = 0
    visible = False
    first = None
    highest = -1
    presented = 0
    finished = False
    try:
        while process.is_running():
            pump()
            now = time.monotonic()
            if now >= next_probe:
                identifier = None
                for f in process.open_files():
                    path = Path(f.path)
                    if path.suffix.lower() == ".stm":
                        identifier = (
                            path.stem.lower() if path.stem.lower() in clips else None
                        )
                        if identifier:
                            break
                next_probe = now + 0.10
                if identifier != clip:
                    if visible:
                        hidden(window, 0)
                    if cap:
                        cap.release()
                    if clip:
                        log(
                            f"end {clip}: frame range {first}..{highest}, {presented} presentations"
                        )
                    clip = identifier
                    cap = None
                    visible = False
                    first = None
                    last = -1
                    highest = -1
                    presented = 0
                    finished = False
                    if clip:
                        cap = cv2.VideoCapture(
                            str(movies / (clip + ".mp4")), cv2.CAP_FFMPEG
                        )
                        if not cap.isOpened():
                            raise RuntimeError(clip)
            # The game replaces its startup window. Find the currently focused
            # game window each time so a stale handle cannot suppress playback.
            hwnd = foreground()
            owner = w.DWORD()
            if hwnd:
                window_pid(hwnd, c.byref(owner))
            if (
                cap
                and owner.value == pid
                and read(handle, base + 0x5A4AC, c.byref(counter), 4, None)
            ):
                index = counter.value
                # The original clears its frame counter before closing the file.
                if index == 0 and highest > 1:
                    finished = True
                    if visible:
                        hidden(window, 0)
                        visible = False
                if (
                    not finished
                    and index < int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    and (index != last or not visible)
                ):
                    next_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                    if next_frame > index or index - next_frame > 12:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                    else:
                        for _ in range(index - next_frame):
                            cap.grab()
                    ok, frame = cap.read()
                    if ok:
                        rect = w.RECT()
                        u.GetClientRect(hwnd, c.byref(rect))
                        pt = w.POINT()
                        u.ClientToScreen(hwnd, c.byref(pt))
                        width = min(rect.right, rect.bottom * 16 // 9)
                        height = width * 9 // 16
                        if width > 0 and height > 0:
                            position(
                                window,
                                -1,
                                pt.x + (rect.right - width) // 2,
                                pt.y + (rect.bottom - height) // 2,
                                width,
                                height,
                                0x0050,
                            )
                            dc = dc_for(window)
                            try:
                                lines = draw(
                                    dc,
                                    0,
                                    0,
                                    width,
                                    height,
                                    0,
                                    0,
                                    1920,
                                    1080,
                                    frame.ctypes.data,
                                    header,
                                    0,
                                    0xCC0020,
                                )
                                if lines <= 0:
                                    raise RuntimeError("Could not present HD frame")
                            finally:
                                release(window, dc)
                            visible = True
                            last = index
                            highest = max(highest, index)
                            presented += 1
                            if first is None:
                                first = index
                                log(f"show {clip} frame {index} size {width}x{height}")
            elif visible:
                hidden(window, 0)
                visible = False
            time.sleep(0.008)
    except psutil.NoSuchProcess:
        pass
    finally:
        if cap:
            cap.release()
        u.DestroyWindow(window)
        k.CloseHandle(handle)


if __name__ == "__main__":
    play(*map(int, sys.argv[1:3]), Path(sys.argv[3]))
