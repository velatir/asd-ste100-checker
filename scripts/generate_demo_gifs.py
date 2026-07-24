#!/usr/bin/env python3
"""Generate README demo GIFs from real ste100 fixture summaries.

Uses host-rendered terminal frames (Pillow + imageio) so demos stay
reproducible without requiring vhs in CI. Output:
  docs/demo-cli.gif
  docs/demo-agent-loop.gif
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FIX = DOCS / "fixtures"

# Light technical terminal (not purple / cream brochure)
BG = (247, 248, 250)
FG = (31, 35, 40)
MUTED = (101, 109, 118)
PROMPT = (9, 105, 218)
ERR = (207, 34, 46)
OK = (26, 127, 55)
CHIP_FG = (164, 14, 38)

W, H = 980, 520
PAD = 22
LINE_H = 22
FPS = 8


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    ):
        p = Path(path)
        if p.is_file():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


FONT = _font(15)
FONT_SM = _font(13)


def _blank() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W - 1, H - 1), outline=(208, 215, 222), width=1)
    draw.text((PAD, 10), "ste100 · terminal demo", font=FONT_SM, fill=MUTED)
    draw.line((PAD, 32, W - PAD, 32), fill=(208, 215, 222), width=1)
    return img


def _wrap(text: str, max_chars: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        while len(raw) > max_chars:
            cut = raw.rfind(" ", 0, max_chars)
            if cut < 20:
                cut = max_chars
            lines.append(raw[:cut])
            raw = raw[cut:].lstrip()
        lines.append(raw)
    return lines


def _draw_lines(
    lines: list[tuple[str, tuple[int, int, int]]],
    *,
    y0: int = 48,
) -> Image.Image:
    img = _blank()
    draw = ImageDraw.Draw(img)
    y = y0
    for text, color in lines:
        for part in _wrap(text):
            if y > H - 28:
                return img
            draw.text((PAD, y), part, font=FONT, fill=color)
            y += LINE_H
    return img


def _type_command(cmd: str, prior: list[tuple[str, tuple[int, int, int]]] | None = None) -> list[Image.Image]:
    frames: list[Image.Image] = []
    base = list(prior or [])
    typed = ""
    # fewer frames while typing for smaller GIF
    step = max(1, len(cmd) // 28)
    for i in range(0, len(cmd) + 1, step):
        typed = cmd[:i]
        lines = base + [(f"$ {typed}█", PROMPT)]
        frames.append(_draw_lines(lines))
    lines = base + [(f"$ {cmd}", PROMPT)]
    frames.append(_draw_lines(lines))
    return frames


def _hold(img: Image.Image, seconds: float) -> list[Image.Image]:
    n = max(1, int(seconds * FPS))
    return [img] * n


def _load_json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def build_cli_frames() -> list[Image.Image]:
    before = _load_json("before-summary.json")
    after = _load_json("after-summary.json")
    samples = _load_json("before-samples.json")

    frames: list[Image.Image] = []
    prior: list[tuple[str, tuple[int, int, int]]] = []

    cmd1 = "ste100 check before.txt --text-type procedure"
    frames.extend(_type_command(cmd1, prior))
    prior.append((f"$ {cmd1}", PROMPT))

    out_lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"compliant: {json.dumps(before['compliant'])}", ERR),
        (f"summary:  {before['summary']['total']} findings "
         f"({before['summary']['error']} error, {before['summary']['warning']} warning)", FG),
        ("rules:", FG),
    ]
    for rule in before["rules"]:
        out_lines.append((f"  • {rule}", CHIP_FG if rule in {
            "STE-VOCAB-UNAPPROVED", "STE-SENTENCE-LENGTH", "STE-PASSIVE"
        } else MUTED))
    out_lines.append(("", FG))
    out_lines.append(("sample findings:", MUTED))
    for s in samples:
        out_lines.append((f"  [{s['severity']}] {s['rule_id']}", ERR if s["severity"] == "error" else (180, 100, 20)))
        out_lines.append((f"    {s['message'][:78]}", MUTED))

    built = list(prior)
    for line in out_lines:
        built.append(line)
        frames.extend(_hold(_draw_lines(built), 0.18))
    frames.extend(_hold(_draw_lines(built), 1.4))

    # Clear for the rewrite recheck so the improvement is readable.
    prior = []
    cmd2 = "ste100 check after.txt --text-type procedure"
    frames.extend(_type_command(cmd2, prior))
    prior = [(f"$ {cmd2}", PROMPT)]

    after_lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"compliant: {json.dumps(after['compliant'])}  (vocab remains without glossary)", MUTED),
        (f"summary:  {after['summary']['total']} findings "
         f"({after['summary']['error']} error) — length/passive cleared", OK),
        ("rules:", FG),
        ("  • STE-VOCAB-UNAPPROVED", MUTED),
        ("", FG),
        ("structure fixed: short imperative steps", OK),
    ]
    built = list(prior)
    for line in after_lines:
        built.append(line)
        frames.extend(_hold(_draw_lines(built), 0.22))
    frames.extend(_hold(_draw_lines(built), 2.2))
    return frames


def build_agent_frames() -> list[Image.Image]:
    """Simulate how an LLM agent drives MCP tools on the fixture text."""
    before = _load_json("before-summary.json")
    after = _load_json("after-summary.json")
    samples = _load_json("before-samples.json")
    before_text = (FIX / "before.txt").read_text(encoding="utf-8").strip()
    after_text = (FIX / "after.txt").read_text(encoding="utf-8").strip()

    frames: list[Image.Image] = []
    scroll: list[tuple[str, tuple[int, int, int]]] = []

    def paint(extra: list[tuple[str, tuple[int, int, int]]] | None = None) -> Image.Image:
        return _draw_lines(scroll + (extra or []), y0=44)

    def hold(seconds: float) -> None:
        frames.extend(_hold(paint(), seconds))

    def add(line: str, color: tuple[int, int, int] = FG, *, pause: float = 0.12) -> None:
        scroll.append((line, color))
        while len(scroll) > 17:
            scroll.pop(0)
        hold(pause)

    def type_tool(call: str) -> None:
        step = max(2, len(call) // 14)
        for i in range(0, len(call) + 1, step):
            frames.append(paint([(call[:i] + "█", PROMPT)]))
        add(call, PROMPT, pause=0.2)

    # Scene 1 — real example text
    add("# MCP agent loop · deploy-docs example", MUTED, pause=0.3)
    add("user: check + rewrite this procedure for STE", MUTED, pause=0.25)
    add('text = """', MUTED, pause=0.08)
    for chunk in _wrap(before_text, max_chars=88):
        add(chunk, FG, pause=0.06)
    add('"""', MUTED, pause=0.35)

    # Scene 2 — ste_check_text
    type_tool('tool → ste_check_text(text, text_type="procedure")')
    add(
        f"← compliant: false · {before['summary']['total']} findings "
        f"({before['summary']['error']}e/{before['summary']['warning']}w)",
        ERR,
        pause=0.2,
    )
    for s in samples:
        sev = ERR if s["severity"] == "error" else (180, 100, 20)
        add(f"  [{s['severity']}] {s['rule_id']}: {s['message'][:58]}", sev, pause=0.15)
    hold(0.7)

    # Scene 3 — ste_suggest_rewrite
    type_tool('tool → ste_suggest_rewrite(text, text_type="procedure")')
    add("← rewrite brief (no LLM API in MCP)", FG, pause=0.15)
    add("  · split long sentences · one instruction each · active voice", MUTED, pause=0.15)
    add("  · STE-SENTENCE-LENGTH (54>20) · VOCAB · PASSIVE", CHIP_FG, pause=0.35)

    # Scene 4 — host LLM rewrite
    add("agent: apply brief → rewrite", PROMPT, pause=0.25)
    for line in after_text.splitlines():
        add(f"  {line}", FG, pause=0.14)
    hold(0.55)

    # Scene 5 — recheck
    type_tool('tool → ste_check_text(rewrite, text_type="procedure")')
    add(
        f"← compliant: false · {after['summary']['total']} findings "
        f"(vocab without glossary)",
        MUTED,
        pause=0.2,
    )
    add("  cleared: SENTENCE-LENGTH · PASSIVE · ONE-INSTRUCTION", OK, pause=0.2)
    add("  remaining: STE-VOCAB-UNAPPROVED", MUTED, pause=0.2)
    add("done: structure fixed · recheck ok · glossary optional", OK, pause=1.4)
    return frames


def _write_gif(path: Path, frames: list[Image.Image]) -> None:
    import shutil
    import subprocess
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = int(1000 / FPS)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.gif"
        frames[0].save(
            raw,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True,
            disposal=2,
        )
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            # Palette-optimized GIF keeps README payloads small on GitHub.
            vf = (
                f"fps={FPS},scale={W}:-1:flags=lanczos,"
                "split[s0][s1];[s0]palettegen=max_colors=48[p];[s1][p]paletteuse=dither=bayer"
            )
            subprocess.run(
                [ffmpeg, "-y", "-i", str(raw), "-vf", vf, str(path)],
                check=True,
                capture_output=True,
            )
        else:
            shutil.copyfile(raw, path)


def main() -> None:
    cli = build_cli_frames()
    agent = build_agent_frames()
    cli_path = DOCS / "demo-cli.gif"
    agent_path = DOCS / "demo-agent-loop.gif"
    _write_gif(cli_path, cli)
    _write_gif(agent_path, agent)
    for p in (cli_path, agent_path):
        kb = p.stat().st_size / 1024
        print(f"wrote {p.relative_to(ROOT)} ({kb:.1f} KiB)")


if __name__ == "__main__":
    main()
