#!/usr/bin/env python3
"""Example client for ocr_service.

Requires Pillow:
    python -m pip install Pillow
"""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import re
import struct
import sys
import time
from pathlib import Path

from PIL import Image

REQUEST_MAGIC = 0x3152434F
RESPONSE_MAGIC = 0x3153434F
PROTOCOL_VERSION = 1
FORMAT_BGRA32 = 1
STATUS_OK = 0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
REQUEST_HEADER = struct.Struct("<IHHIIIIQ")
RESPONSE_HEADER = struct.Struct("<IHHIIIIQ")


def read_exact(pipe, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = pipe.read(size - len(chunks))
        if not chunk:
            raise RuntimeError("named pipe closed while reading")
        chunks.extend(chunk)
    return bytes(chunks)


def write_all(pipe, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = pipe.write(data[offset:])
        if written is None:
            written = len(data) - offset
        if written <= 0:
            raise RuntimeError("named pipe closed while writing")
        offset += written
    pipe.flush()


def normalize_pipe_name(value: str) -> str:
    """Accept the canonical name and the over-escaped config form."""
    leading = len(value) - len(value.lstrip("\\"))
    if leading < 2:
        raise ValueError("pipe name must start with \\\\.\\pipe\\")
    rest = re.sub(r"\\+", r"\\", value[leading:])
    normalized = r"\\" + rest
    prefix = "\\\\" + ".\pipe" + "\\"
    if not normalized.startswith(prefix) or len(normalized) <= len(prefix):
        raise ValueError("pipe name must use the form \\\\.\\pipe\\name")
    return normalized


def load_bgra(
    path: Path,
    crop: tuple[int, int, int, int] | None,
    mode: str = "bgra",
) -> tuple[int, int, bytes, dict[str, float]]:
    read_started = time.perf_counter()
    with path.open("rb") as source_file:
        encoded = source_file.read()
    with Image.open(BytesIO(encoded)) as source:
        source.load()
        source_image = source.copy()
    read_ms = (time.perf_counter() - read_started) * 1000

    conversion_started = time.perf_counter()
    if mode == "bgra":
        image = source_image.convert("RGBA")
    elif mode == "no-alpha":
        image = source_image.convert("RGB")
    else:
        raise ValueError(f"unsupported benchmark mode: {mode}")
    if crop is not None:
        x, y, width, height = crop
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("crop requires non-negative x/y and positive width/height")
        if x + width > image.width or y + height > image.height:
            raise ValueError("crop rectangle is outside the input image")
        image = image.crop((x, y, x + width, y + height))
    if mode == "bgra":
        pixels = image.tobytes("raw", "BGRA")
    else:
        alpha = Image.new("L", image.size, 255)
        rgba = Image.merge("RGBA", (*image.split(), alpha))
        pixels = rgba.tobytes("raw", "BGRA")
    conversion_ms = (time.perf_counter() - conversion_started) * 1000
    timings = {"read_ms": read_ms, "conversion_ms": conversion_ms}
    return image.width, image.height, pixels, timings


def request(
    pipe,
    width: int,
    height: int,
    pixels: bytes,
    request_id: int,
    emit_status: bool = True,
) -> tuple[int, dict, dict[str, float]]:
    stride = width * 4
    header = REQUEST_HEADER.pack(
        REQUEST_MAGIC,
        PROTOCOL_VERSION,
        FORMAT_BGRA32,
        width,
        height,
        stride,
        len(pixels),
        request_id,
    )
    send_started = time.perf_counter()
    write_all(pipe, header)
    write_all(pipe, pixels)
    send_ms = (time.perf_counter() - send_started) * 1000

    compute_started = time.perf_counter()
    response_header = read_exact(pipe, RESPONSE_HEADER.size)
    compute_ms = (time.perf_counter() - compute_started) * 1000
    magic, version, _reserved, status, response_width, response_height, json_bytes, response_id = RESPONSE_HEADER.unpack(response_header)
    if magic != RESPONSE_MAGIC or version != PROTOCOL_VERSION:
        raise RuntimeError("invalid response header")
    if response_id != request_id:
        raise RuntimeError(f"response requestId mismatch: expected {request_id}, got {response_id}")
    if json_bytes > MAX_RESPONSE_BYTES:
        raise RuntimeError("response JSON is too large")
    receive_started = time.perf_counter()
    payload = read_exact(pipe, json_bytes)
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("service returned invalid UTF-8 JSON") from error
    receive_ms = (time.perf_counter() - receive_started) * 1000
    if emit_status:
        print(
            f"status={status} image={response_width}x{response_height} requestId={response_id}",
            file=sys.stderr,
        )
    timings = {
        "send_ms": send_ms,
        "compute_ms": compute_ms,
        "receive_ms": receive_ms,
        "roundtrip_ms": send_ms + compute_ms + receive_ms,
    }
    return status, result, timings


def print_benchmark_summary(mode: str, samples: list[dict[str, float]]) -> None:
    fields = ("read_ms", "conversion_ms", "send_ms", "compute_ms", "receive_ms", "roundtrip_ms")
    print(f"[{mode}]")
    for field in fields:
        values = [sample[field] for sample in samples]
        average = sum(values) / len(values)
        print(f"{field:16s} avg={average:8.3f} ms min={min(values):8.3f} ms max={max(values):8.3f} ms")


def run_benchmark(args: argparse.Namespace, crop: tuple[int, int, int, int] | None) -> int:
    modes = ("bgra", "no-alpha") if args.benchmark_mode == "both" else (args.benchmark_mode,)
    pipe_name = normalize_pipe_name(args.pipe_name)
    exit_code = 0
    next_request_id = args.request_id
    for mode in modes:
        samples = []
        with open(pipe_name, "r+b", buffering=0) as pipe:
            for index in range(args.benchmark_warmup + args.benchmark_repeat):
                width, height, pixels, load_timings = load_bgra(args.input, crop, mode)
                status, result, request_timings = request(
                    pipe,
                    width,
                    height,
                    pixels,
                    next_request_id,
                    emit_status=False,
                )
                next_request_id += 1
                if status != STATUS_OK or not result.get("ok", False):
                    exit_code = 2
                if index >= args.benchmark_warmup:
                    samples.append({**load_timings, **request_timings})
        print_benchmark_summary(mode, samples)
    return exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an image to pixpin_ocr_service")
    parser.add_argument("--input", required=True, type=Path, help="JPG/PNG/BMP input image")
    parser.add_argument("--pipe-name", default=r"\\.\pipe\pixpin-ocr")
    parser.add_argument("--crop", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--request-id", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=1, help="send repeatedly on one pipe connection")
    parser.add_argument("--benchmark", action="store_true", help="measure file, conversion, request, OCR wait, and response stages")
    parser.add_argument("--benchmark-mode", choices=("bgra", "no-alpha", "both"), default="both")
    parser.add_argument("--benchmark-repeat", type=int, default=3, help="measured requests per benchmark mode")
    parser.add_argument("--benchmark-warmup", type=int, default=1, help="unmeasured requests per benchmark mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise RuntimeError(f"input image does not exist: {args.input}")
    if args.repeat <= 0 or args.benchmark_repeat <= 0 or args.benchmark_warmup < 0:
        raise RuntimeError("--repeat must be positive")
    crop = tuple(args.crop) if args.crop is not None else None
    if args.benchmark:
        return run_benchmark(args, crop)
    width, height, pixels, _load_timings = load_bgra(args.input, crop)

    # On Windows, open() can open a named pipe using its Win32 path.
    pipe_name = normalize_pipe_name(args.pipe_name)
    with open(pipe_name, "r+b", buffering=0) as pipe:
        exit_code = 0
        for index in range(args.repeat):
            status, result, _request_timings = request(pipe, width, height, pixels, args.request_id + index)
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            if status != STATUS_OK or not result.get("ok", False):
                exit_code = 2
        return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"pixpin_ocr_python_client: {error}", file=sys.stderr)
        raise SystemExit(1)
