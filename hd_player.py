"""Display the HD frame matching the English ISO game's own movie counter."""

import ctypes as c
import hashlib
import struct
import sys
import tempfile
import time
from contextlib import ExitStack
from ctypes import wintypes as w
from pathlib import Path

import cv2
import numpy as np
import psutil
from build_cinematics import video_stream

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
memory_dc = api(g, "CreateCompatibleDC", ptr, ptr)
dib = api(g, "CreateDIBSection", ptr, ptr, ptr, w.UINT, c.POINTER(ptr), ptr, w.DWORD)
select = api(g, "SelectObject", ptr, ptr, ptr)
delete_bitmap = api(g, "DeleteObject", w.BOOL, ptr)
delete_dc = api(g, "DeleteDC", w.BOOL, ptr)
update = api(
    u,
    "UpdateLayeredWindow",
    w.BOOL,
    ptr,
    ptr,
    ptr,
    ptr,
    ptr,
    ptr,
    w.DWORD,
    ptr,
    w.DWORD,
)
position = api(
    u, "SetWindowPos", w.BOOL, ptr, ptr, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT
)


class Surface:
    """Complete each frame off screen before handing its bitmap to Windows."""

    def __init__(self, width, height):
        self.size = w.SIZE(width, height)
        header = struct.pack(
            "<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0
        )
        self.dc = memory_dc(None)
        address = ptr()
        self.bitmap = dib(self.dc, header, 0, c.byref(address), None, 0)
        if not self.bitmap:
            delete_dc(self.dc)
            raise c.WinError()
        self.old = select(self.dc, self.bitmap)
        self.pixels = np.ctypeslib.as_array(
            (c.c_uint8 * (width * height * 4)).from_address(address.value)
        ).reshape(height, width, 4)

    def close(self):
        select(self.dc, self.old)
        delete_bitmap(self.bitmap)
        delete_dc(self.dc)

    def present(self, window, origin):
        zero = w.POINT()
        if not update(
            window,
            None,
            c.byref(origin),
            c.byref(self.size),
            self.dc,
            c.byref(zero),
            0,
            None,
            4,
        ):
            raise c.WinError()


set_owner = api(
    u,
    "SetWindowLongPtrW" if c.sizeof(ptr) == 8 else "SetWindowLongW",
    ptr,
    ptr,
    c.c_int,
    ptr,
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


# Query only the five local movie files. Enumerating every handle in the
# game repeatedly can exhaust the Windows guest's thread/commit budget.
open_attributes = api(
    k, "CreateFileW", ptr, w.LPCWSTR, w.DWORD, w.DWORD, ptr, w.DWORD, w.DWORD, ptr
)
query_file = api(
    c.windll.ntdll, "NtQueryInformationFile", w.LONG, ptr, ptr, ptr, w.ULONG, w.ULONG
)
close_handle = api(k, "CloseHandle", w.BOOL, ptr)


def game_has_movie(path, pid):
    handle = open_attributes(str(path), 0x80, 7, None, 3, 0, None)
    if handle == c.c_void_p(-1).value:
        raise c.WinError()
    try:
        # FileProcessIdsUsingFileInformation returns a ULONG count followed
        # by pointer-aligned process IDs. The status block reports byte length.
        io_status = (c.c_size_t * 2)()
        size = 256
        while True:
            buf = c.create_string_buffer(size)
            status = query_file(handle, io_status, buf, size, 47) & 0xFFFFFFFF
            if status in (0xC0000004, 0x80000005) and size < 65536:
                size *= 2
                continue
            if status:
                raise OSError(f"Movie handle query failed (NTSTATUS 0x{status:08X})")
            count = w.ULONG.from_buffer(buf).value
            offset = c.sizeof(ptr)
            if count and (count + 1) * offset > min(size, io_status[1]):
                raise ValueError("Incomplete movie process list")
            return pid in (c.c_size_t * count).from_buffer(buf, offset)
    finally:
        close_handle(handle)


def play(pid, base, runtime, resources):
    process = psutil.Process(pid)
    identity = hashlib.sha256(Path(process.exe()).read_bytes()).hexdigest()
    if identity not in {
        "90cd971aff6570ae508d3011c6a0a84b9f61b433f3fef568bbf5854f14de9dd8",
        "25a90fec1fb0adc33cd51161c23f48e712c2d3298fcd823a6a583da1ad6487a7",
    }:
        raise ValueError("Unsupported cinematic build")
    handle = open_read(0x10, False, pid)
    if not handle:
        raise c.WinError()
    # The standard STATIC class supplies a non-interactive display surface.
    window = create(
        0x080800A0,  # Non-activating, click-through, layered tool window
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
    game_window = None
    movies = runtime.parent / "HD-Cinematics"
    clips = {
        name: runtime / "Title" / (name + ".stm")
        for name in ("rf", "win", "win1", "win2", "win3")
        if (movies / (name + ".mp4")).is_file()
    }
    sources = {name: movies / (name + ".mp4") for name in clips}
    scratch = Path(resources.enter_context(tempfile.TemporaryDirectory()))
    for name, digest in {
        "prolific": "f64e28c87af5c3cd7a846350b3783cf95fdcbeeaed79c4bb4e1406b926707140",
        "twi": "f3ba15654eba1d605b342abb2d53944b77ac31a9871c004021bc05a394b7ee1d",
    }.items():
        stm = runtime / "Title" / (name + ".stm")
        if stm.is_file():
            data = stm.read_bytes()
            if hashlib.sha256(data).hexdigest() == digest:
                avi = scratch / (name + ".avi")
                avi.write_bytes(
                    video_stream(data, struct.unpack_from("<I", data, 216)[0], b"")
                )
                sources[name] = avi
                clips[name] = stm
    banner = cv2.imdecode(
        np.fromfile(runtime / "Title" / "BanBH.BMP", dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if banner is None:
        raise ValueError("Could not read the original victory banner")
    surface = None
    counter = c.c_uint32()
    cap = None
    clip = None
    last = -1
    probe_failed = False
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
                try:
                    identifier = next(
                        (
                            name
                            for name, path in clips.items()
                            if game_has_movie(path, pid)
                        ),
                        None,
                    )
                except OSError as exc:
                    if not probe_failed:
                        log(f"Movie detection temporarily unavailable: {exc}")
                    probe_failed = True
                    next_probe = now + 1
                    hidden(window, 0)
                    visible = False
                    continue
                probe_failed = False
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
                        cap = cv2.VideoCapture(str(sources[clip]), cv2.CAP_FFMPEG)
                        if not cap.isOpened():
                            raise RuntimeError(clip)
            if probe_failed:
                time.sleep(0.05)
                continue
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
                            if game_window != hwnd:
                                # An owned popup stays above its game window even when the
                                # renderer raises the game during the victory transition.
                                k.SetLastError(0)
                                if not set_owner(window, -8, hwnd) and k.GetLastError():
                                    raise c.WinError()
                                game_window = hwnd
                            victory = clip.startswith("win")
                            film_width = (
                                width
                                if clip == "rf"
                                else min(width, height * 4 // 3)
                            )
                            film_height = film_width * frame.shape[0] // frame.shape[1]
                            inset_x = (width - film_width) // 2
                            inset_y = (height - film_height) // 2
                            if surface is None or (
                                surface.size.cx,
                                surface.size.cy,
                            ) != (width, height):
                                if surface:
                                    surface.close()
                                surface = Surface(width, height)
                            surface.pixels.fill(0)
                            film = cv2.resize(
                                frame,
                                (film_width, film_height),
                                interpolation=cv2.INTER_AREA
                                if film_width < frame.shape[1]
                                else cv2.INTER_LINEAR,
                            )
                            surface.pixels[
                                inset_y : inset_y + film_height,
                                inset_x : inset_x + film_width,
                                :3,
                            ] = film
                            if victory:
                                # Original single-player brown banner, 360x104 on the 480-line surface.
                                bw = round(360 * height / 480)
                                bh = round(104 * height / 480)
                                bx = (width - bw) // 2
                                by = round(363 * height / 480)
                                badge = cv2.resize(
                                    banner, (bw, bh), interpolation=cv2.INTER_NEAREST
                                )
                                target = surface.pixels[by : by + bh, bx : bx + bw, :3]
                                np.copyto(
                                    target,
                                    badge,
                                    where=np.any(badge, axis=2)[:, :, None],
                                )
                            origin = w.POINT(
                                pt.x + (rect.right - width) // 2,
                                pt.y + (rect.bottom - height) // 2,
                            )
                            surface.present(window, origin)
                            if not visible and not position(
                                window, -1, 0, 0, 0, 0, 0x0053
                            ):
                                raise c.WinError()
                            visible = True
                            last = index
                            highest = max(highest, index)
                            presented += 1
                            if first is None:
                                first = index
                                log(
                                    f"show {sources[clip].name} frame {index} "
                                    f"source {frame.shape[1]}x{frame.shape[0]} "
                                    f"display {film_width}x{film_height} at "
                                    f"{pt.x + (rect.right - width) // 2 + inset_x},"
                                    f"{pt.y + (rect.bottom - height) // 2 + inset_y}"
                                )
            elif visible:
                hidden(window, 0)
                visible = False
            time.sleep(0.008)
    except psutil.NoSuchProcess:
        pass
    finally:
        if cap:
            cap.release()
        if surface:
            surface.close()
        u.DestroyWindow(window)
        k.CloseHandle(handle)


if __name__ == "__main__":
    with ExitStack() as resources:
        play(*map(int, sys.argv[1:3]), Path(sys.argv[3]), resources)
