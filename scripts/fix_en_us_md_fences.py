#!/usr/bin/env python3
"""Post-process en-US markdown: restore newlines mangled by machine translation."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "en-US"

LANG = r"shell|sql|yaml|bash|python|text|json|ini|toml"
LANG_WORDS = frozenset(
    w
    for w in "shell sql yaml bash python text json ini toml".split()
)


def _close_fence_before_prose(m: re.Match[str]) -> str:
    word = m.group(1)
    if word.lower() in LANG_WORDS:
        return m.group(0)
    return "```\n\n" + word + m.group(2)


def fix_one(content: str) -> str:
    s = content

    s = s.replace("</main>```", "</main>\n\n```")

    # Closing ``` immediately followed by prose (not ```shell etc.)
    s = re.sub(rf"```([A-Za-z][A-Za-z]{{1,24}})([\s\.,:;\!\?，。、])", _close_fence_before_prose, s)

    # ```###heading -> close fence, then ### heading (missing space)
    s = re.sub(r"```(#{1,6})([A-Za-z\u4e00-\u9fff])", r"```\n\n\1 \2", s)

    # ```### heading -> close fence, then heading
    s = re.sub(r"```(#+\s)", r"```\n\n\1", s)

    # Heading or prose immediately followed by opening fence
    s = re.sub(rf"([^\n#`])(```({LANG}))(\s+script)?", r"\1\n\n\2", s)
    s = re.sub(rf"(#{1,6}[^\n`]+)(```({LANG}))(\s+script)?", r"\1\n\n\2", s)

    # Normalize ```shell script -> ```shell (GitHub-flavored)
    s = re.sub(r"```shell\s+script\b", "```shell", s)

    # ###Word -> ### Word
    s = re.sub(r"(^|\n)(#{1,6})([A-Za-z\u4e00-\u9fff])", r"\1\2 \3", s, flags=re.MULTILINE)

    # Double-space after ### if we introduced "#### " incorrectly - skip

    # Erroneous line-start ``` immediately before English text (orphan opener)
    s = re.sub(r"\n```([A-Z][a-z]+(?:\s+[a-z]+){0,4})\n", r"\n\1\n", s)

    return s


def main() -> None:
    paths = sorted(EN.rglob("*.md"))
    changed = 0
    for p in paths:
        raw = p.read_text(encoding="utf-8", errors="replace")
        fixed = fix_one(raw)
        if fixed != raw:
            p.write_text(fixed, encoding="utf-8")
            changed += 1
            print(p.relative_to(ROOT), file=sys.stderr)
    print(f"Updated {changed} files", file=sys.stderr)


if __name__ == "__main__":
    main()
