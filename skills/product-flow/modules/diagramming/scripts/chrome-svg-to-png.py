#!/usr/bin/env python3
"""Render an SVG to PNG with an installed Chromium-family browser.

This is SYBuilder's dependency-free fallback when CairoSVG and librsvg are
unavailable.  It deliberately uses only the Python standard library and a
locally installed browser; it never downloads a renderer at runtime.
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET


MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def browser() -> str | None:
    explicit = os.environ.get("CHROME_BIN")
    if explicit and Path(explicit).is_file():
        return explicit
    if MAC_CHROME.is_file():
        return str(MAC_CHROME)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def _number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", value)
    return float(match.group(1)) if match else None


def dimensions(svg: Path, target_width: int) -> tuple[int, int]:
    root = ET.parse(svg).getroot()
    view_box = root.attrib.get("viewBox", "").split()
    if len(view_box) == 4:
        source_width, source_height = float(view_box[2]), float(view_box[3])
    else:
        source_width = _number(root.attrib.get("width")) or float(target_width)
        source_height = _number(root.attrib.get("height")) or source_width * 0.625
    if source_width <= 0 or source_height <= 0:
        raise ValueError("SVG width/height must be positive")
    return target_width, max(1, round(target_width * source_height / source_width))


def render(svg: Path, output: Path, width: int) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
    from _image import validate_image
    chrome = browser()
    if not chrome:
        raise RuntimeError("no local Chrome/Chromium renderer found")

    viewport_width, viewport_height = dimensions(svg, width)
    encoded = base64.b64encode(svg.read_bytes()).decode("ascii")
    html = (
        "<!doctype html><meta charset=utf-8><style>"
        "html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}"
        "img{display:block;width:100%;height:100%;object-fit:contain}"
        "</style><img src=\"data:image/svg+xml;base64," + encoded + "\">"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sybuilder-svg-") as tmp:
        # Chrome may hand a command to an already running desktop instance and
        # return success without writing the screenshot. A dedicated profile
        # forces this render to stay in its own headless process.
        page = Path(tmp) / "render.html"
        profile = Path(tmp) / "profile"
        screenshot = Path(tmp) / "render.png"
        page.write_text(html, encoding="utf-8")
        command = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--virtual-time-budget=3000",
            "--no-first-run",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={viewport_width},{viewport_height}",
            f"--screenshot={screenshot}",
            page.resolve().as_uri(),
        ]
        log = tempfile.TemporaryFile(mode='w+t')
        process = subprocess.Popen(command, stdout=log, stderr=log, text=True)
        completion = 'natural-exit'
        try:
            deadline = time.monotonic() + 60
            complete = False
            while time.monotonic() < deadline:
                code = process.poll()
                if code is not None and code != 0:
                    break
                if screenshot.is_file() and screenshot.read_bytes().endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82'):
                    try:
                        validate_image(screenshot)
                        complete = True
                        break
                    except ValueError:
                        pass  # Writer may still be producing the image.
                if code is not None: break
                time.sleep(0.1)
            code = process.poll()
            if not complete or (code is not None and code != 0):
                log.seek(0)
                detail = log.read().strip()[-800:]
                raise RuntimeError(f"Chrome render failed: {detail or 'no PNG produced'}")
            if code is None:
                completion = 'decoded-image-then-owned-process-cleanup'
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.close()

        validate_image(screenshot)
        png = screenshot.read_bytes()
        if not (png.startswith(b"\x89PNG\r\n\x1a\n") and png.endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82')):
            raise RuntimeError("Chrome output is not a PNG; previous image preserved")
        # Publish only a completed valid render; failed reruns preserve the prior image.
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.png', delete=False) as handle:
            staged = Path(handle.name)
        try:
            shutil.copyfile(screenshot, staged)
            os.replace(staged, output)
        finally:
            staged.unlink(missing_ok=True)
        print('Chrome completion: ' + completion)

    if not output.is_file() or output.stat().st_size < 8:
        raise RuntimeError("Chrome reported success but produced no PNG")
    if output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Chrome output is not a PNG")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("png", type=Path)
    parser.add_argument("--width", type=int, default=1920)
    args = parser.parse_args()
    if args.width <= 0:
        parser.error("--width must be positive")
    try:
        render(args.svg.resolve(), args.png.resolve(), args.width)
    except Exception as exc:
        print(f"UNABLE: {exc}")
        return 2
    print(args.png.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
