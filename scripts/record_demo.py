#!/usr/bin/env python3
"""Genera la demo GIF/MP4 con Playwright y datos ficticios.

Uso:
    uv run python scripts/record_demo.py
    uv run python scripts/record_demo.py --output-dir /tmp/demo
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.e2e.runtime import (  # noqa: E402
    construir_entorno,
    detener_servidor,
    flujo_demo,
    iniciar_servidor,
    preparar_base,
)


def _convertir(webm: Path, salida: Path) -> tuple[Path, Path]:
    salida.mkdir(parents=True, exist_ok=True)
    mp4 = salida / "demo.mp4"
    gif = salida / "demo.gif"
    if shutil.which("ffmpeg") is None:
        destino = salida / "demo.webm"
        shutil.copy2(webm, destino)
        print(f"ffmpeg no disponible; se guardó {destino}")
        return destino, destino
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(webm),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(webm),
            "-vf",
            "fps=8,scale=960:-1:flags=lanczos",
            "-loop",
            "0",
            str(gif),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return mp4, gif


def main() -> int:
    parser = argparse.ArgumentParser(description="Grabar demo de la app")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "docs" / "demo"),
    )
    args = parser.parse_args()
    salida = Path(args.output_dir).expanduser()

    with tempfile.TemporaryDirectory(prefix="f31-video-") as tmp:
        tmp_path = Path(tmp)
        env, credenciales = construir_entorno(tmp_path)
        preparar_base(env)
        proceso, base = iniciar_servidor(env)
        video_dir = tmp_path / "video"
        try:
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(
                        channel="chrome",
                        headless=True,
                    )
                except Exception:
                    browser = playwright.chromium.launch(headless=True)
                contexto = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    locale="es-AR",
                    record_video_dir=str(video_dir),
                    record_video_size={"width": 1280, "height": 720},
                )
                page = contexto.new_page()
                try:
                    flujo_demo(page, base, credenciales, pausa_ms=3000)
                finally:
                    video = page.video
                    contexto.close()
                    browser.close()
                if video is None:
                    raise RuntimeError("Playwright no generó video.")
                webm = Path(video.path())
                mp4, gif = _convertir(webm, salida)
        finally:
            detener_servidor(proceso)

    print(f"Video: {mp4}")
    print(f"Preview: {gif}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
