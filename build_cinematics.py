"""Convert the five supported English ISO STM films to 1080p MP4."""

import argparse
import hashlib
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

FILMS = {
    "rf": "fdded7328ea1a554a4f6429ec3e474620b2d87ac417fb028cfa2abe8ee889370",
    "win": "63efe17a67d3b123f05f9f2be8eb5f3b17be43a1b9d29155dd49ba92d044d813",
    "win1": "a469ba4e63c81f468d59e44bfcec5e5045baf528171a86eeda4b37ea273d6e70",
    "win2": "c0773baeab5a38145a842f5ae45829e76dc94c3ec0aaa5c84940cb93e55a0ef1",
    "win3": "96db1fb16eece7e286a2d5177aa4fb9f57a7a1405a6e93b1c2dc68d83c766d84",
}


def chunk(tag, payload):
    return tag + struct.pack("<I", len(payload)) + payload + bytes(len(payload) % 2)


def video_stream(data, total, palette):
    frames = []
    offset = 0
    while True:
        dims = data.find(b"\x01\x40\x00\xf0", offset)
        if dims < 0:
            break
        offset = dims + 4
        start = dims - 4
        size = int.from_bytes(data[start + 1 : dims], "big")
        if (
            start >= 0
            and data[start] in (0, 1)
            and data[dims + 4 : dims + 6] in (b"\0\1", b"\0\2", b"\0\3")
            and data[dims + 6] in (16, 17)
            and 20 < size < 100000
            and start + size <= len(data)
        ):
            frames.append(chunk(b"00dc", data[start : start + size]))
            offset = start + size
    if len(frames) != total:
        raise ValueError(f"Expected {total} Cinepak frames, found {len(frames)}")
    avi = struct.pack("<14I", 66667, 0, 0, 0, total, 0, 1, 0, 320, 240, 0, 0, 0, 0)
    stream = struct.pack(
        "<4s4sIHH8I4h",
        b"vids",
        b"cvid",
        0,
        0,
        0,
        0,
        1,
        15,
        0,
        total,
        100000,
        0xFFFFFFFF,
        0,
        0,
        0,
        320,
        240,
    )
    fmt = struct.pack(
        "<IiiHH4sIiiII",
        40,
        320,
        240,
        1,
        8 if palette else 24,
        b"cvid",
        230400,
        0,
        0,
        256 if palette else 0,
        0,
    )
    headers = chunk(b"avih", avi) + chunk(
        b"LIST", b"strl" + chunk(b"strh", stream) + chunk(b"strf", fmt + palette)
    )
    return chunk(
        b"RIFF",
        b"AVI "
        + chunk(b"LIST", b"hdrl" + headers)
        + chunk(b"LIST", b"movi" + b"".join(frames)),
    )


def convert(name, data, scratch, output):
    total = struct.unpack_from("<I", data, 216)[0]
    palette = data[0x594:0x994] if name == "rf" else b""
    avi, wav = scratch / "source.avi", scratch / "source.wav"
    avi.write_bytes(video_stream(data, total, palette))
    first, page = struct.unpack_from("<II", data)
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((2, 2, 22050, 0, "NONE", ""))
        for pos in range(first, len(data), page):
            offset, samples = struct.unpack_from("<II", data, pos + 8)
            audio.writeframesraw(data[pos + offset : pos + offset + samples * 4])
        if audio.getnframes() != struct.unpack_from("<I", data, 44)[0]:
            raise ValueError("Incomplete source audio")
    ffmpeg = ["ffmpeg", "-nostdin", "-v", "error", "-xerror"]
    source = ["-i", str(avi)]
    if palette:
        # Clamp reserved Windows palette entries at the two ends of the fire ramp.
        colors = bytearray(palette)
        colors[:40] = colors[40:44] * 10
        colors[984:] = colors[980:984] * 10
        colors[3::4] = bytes([255]) * 256
        raw = scratch / "title.pal8"
        subprocess.run(
            ffmpeg + source + ["-f", "rawvideo", "-pix_fmt", "pal8", str(raw)],
            check=True,
        )
        stride = 320 * 240 + 1024
        if raw.stat().st_size != stride * total:
            raise ValueError("Incomplete decoded title")
        with raw.open("r+b") as file:
            for index in range(total):
                file.seek((index + 1) * stride - 1024)
                file.write(colors)
        source = [
            "-f",
            "rawvideo",
            "-pixel_format",
            "pal8",
            "-video_size",
            "320x240",
            "-framerate",
            "15",
            "-i",
            str(raw),
        ]
    top = 30 if palette else 56
    filters = f"format=rgb24,crop=320:180:0:{top},scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p"
    subprocess.run(
        ffmpeg
        + source
        + [
            "-i",
            str(wav),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-vf",
            filters,
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output / (name + ".mp4")),
        ],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Mounted or extracted English ISO root"
    )
    parser.add_argument("output", type=Path, help="New private output directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists. Choose a new directory to rebuild.")
    if not shutil.which("ffmpeg"):
        parser.error("Install FFmpeg with libx264 support and add it to PATH.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        scratch = Path(tmp)
        staged = scratch / "finished"
        staged.mkdir()
        for name, digest in FILMS.items():
            data = (args.source / "Title" / (name + ".stm")).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(
                    f"Unsupported or incomplete English ISO film: {name}.stm"
                )
            print(f"Building {name}.mp4", flush=True)
            convert(name, data, scratch, staged)
        staged.rename(args.output)


if __name__ == "__main__":
    main()
