#!/usr/bin/env python3
"""
Translate zh-CN markdown into en-US for paths missing or shorter in en-US.
Preserves ``` fenced code blocks ``` untranslated.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = ROOT / "zh-CN"
EN = ROOT / "en-US"

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Install: python3 -m venv .venv-trans && .venv-trans/bin/pip install deep-translator", file=sys.stderr)
    sys.exit(1)

ZH_CHAR = re.compile(r"[\u4e00-\u9fff]")
FENCE = re.compile(r"(```[\s\S]*?```)")


def list_zh_rel_paths() -> list[str]:
    out = subprocess.check_output(
        ["bash", "-c", f"cd {ZH} && find . -type f -name '*.md' | sed 's|^\\./||' | sort"],
        text=True,
    )
    return [p for p in out.splitlines() if p.strip()]


def list_en_rel_paths() -> set[str]:
    out = subprocess.check_output(
        ["bash", "-c", f"cd {EN} && find . -type f -name '*.md' | sed 's|^\\./||' | sort"],
        text=True,
    )
    return {p.strip() for p in out.splitlines() if p.strip()}


def translate_text(translator: GoogleTranslator, text: str, sleep_s: float) -> str:
    if not text or not ZH_CHAR.search(text):
        return text
    max_chunk = 4200
    buf = ""
    chunks: list[str] = []
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > max_chunk and buf:
            chunks.append(buf)
            buf = line
        else:
            buf += line
    if buf:
        chunks.append(buf)

    out_parts: list[str] = []
    for ch in chunks:
        if not ZH_CHAR.search(ch):
            out_parts.append(ch)
            continue
        for attempt in range(4):
            try:
                out_parts.append(translator.translate(ch))
                break
            except Exception as e:
                wait = (attempt + 1) * 2.0
                print(f"  translate retry {attempt+1} after error: {e!s}", file=sys.stderr)
                time.sleep(wait)
        else:
            print("  FAILED chunk, keeping Chinese", file=sys.stderr)
            out_parts.append(ch)
        time.sleep(sleep_s)
    return "".join(out_parts)


def translate_markdown(translator: GoogleTranslator, content: str, sleep_s: float) -> str:
    parts = FENCE.split(content)
    result: list[str] = []
    for part in parts:
        if part.startswith("```"):
            result.append(part)
        else:
            result.append(translate_text(translator, part, sleep_s) if part else part)
    return "".join(result)


def line_count(p: Path) -> int:
    if not p.is_file():
        return 0
    return sum(1 for _ in p.open(encoding="utf-8", errors="replace"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=0.15, help="Delay between API calls (seconds)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    zh_paths = list_zh_rel_paths()
    en_set = list_en_rel_paths()
    translator = GoogleTranslator(source="zh-CN", target="en")

    todo: list[tuple[str, str]] = []  # (rel, reason)

    for rel in zh_paths:
        if rel not in en_set:
            todo.append((rel, "missing"))
        else:
            zc = line_count(ZH / rel)
            ec = line_count(EN / rel)
            if zc > ec + 8:
                todo.append((rel, f"shorter_en zc={zc} ec={ec}"))

    print(f"Files to process: {len(todo)}", file=sys.stderr)
    for rel, reason in todo:
        zpath = ZH / rel
        epath = EN / rel
        print(f"{reason}: {rel}", file=sys.stderr)
        content = zpath.read_text(encoding="utf-8", errors="replace")
        if args.dry_run:
            continue
        translated = translate_markdown(translator, content, args.sleep)
        epath.parent.mkdir(parents=True, exist_ok=True)
        epath.write_text(translated, encoding="utf-8")
        print(f"  wrote {epath}", file=sys.stderr)

    if args.dry_run:
        for rel, reason in todo:
            print(f"{reason}\t{rel}")
        return

    # Repair newlines around ``` fences after machine translation
    fix_script = Path(__file__).resolve().parent / "fix_en_us_md_fences.py"
    subprocess.run([sys.executable, str(fix_script)], cwd=str(ROOT), check=False)


if __name__ == "__main__":
    main()
