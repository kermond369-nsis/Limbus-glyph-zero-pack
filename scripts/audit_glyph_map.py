#!/usr/bin/env python3
"""Lint assets/glyph_map.json + optional corpus coverage audit.

Usage:
  python3 scripts/audit_glyph_map.py
  python3 scripts/audit_glyph_map.py --corpus /path/to/LimbusLocalize.zip

Checks:
  - every single-char key is a CJK ideograph or an allowlisted full-width symbol
    (catches copy/paste or extraction errors like "2" -> "1")
  - every replacement value char is inside assets/safe_charset.txt
    (so the value itself is displayable)
  - multi-char (phrase) keys are listed for review
  - with --corpus: dry-run apply over the LLC_zh-CN corpus and report any
    non-ASCII char left outside safe charset / Hangul / ASCII
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "assets/glyph_map.json"
DEFAULT_SAFE = ROOT / "assets/safe_charset.txt"

# full-width symbols we intentionally allow as single-char keys
FULLWIDTH_OK = set("《》＆；？！，。、：；“”‘’（）【】—…")

def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) or (0xF900 <= o <= 0xFAFF) or (0x20000 <= o <= 0x3FFFF)

def is_hangul(ch: str) -> bool:
    o = ord(ch)
    return (0xAC00 <= o <= 0xD7AF) or (0x1100 <= o <= 0x11FF) or (0x3130 <= o <= 0x318F)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=str(DEFAULT_MAP))
    ap.add_argument("--safe-charset", default=str(DEFAULT_SAFE))
    ap.add_argument("--corpus", default="", help="optional 零协 archive (.zip) for dry-run coverage")
    args = ap.parse_args()

    data = json.loads(Path(args.map).read_text(encoding="utf-8"))
    gm = data.get("map") or {}
    safe = set(Path(args.safe_charset).read_text(encoding="utf-8"))

    print(f"glyph_map version: {data.get('version')}")
    print(f"entries: {len(gm)}")
    single = {k: v for k, v in gm.items() if len(k) == 1}
    phrase = {k: v for k, v in gm.items() if len(k) > 1}
    print(f"  single: {len(single)}   phrase: {len(phrase)}")

    errors: list[str] = []
    warns: list[str] = []

    # 1. key sanity
    for k in single:
        if not (is_cjk(k) or k in FULLWIDTH_OK):
            warns.append(f"single-char key not CJK/fullwidth: {k!r} -> {single[k]!r}")
    # 2. value chars must be inside safe charset (or hangul/ascii, which are inherently allowed)
    for k, v in gm.items():
        for ch in v:
            o = ord(ch)
            if o < 128 or is_hangul(ch):
                continue
            if ch not in safe:
                errors.append(f"value char not in safe charset: key={k!r} value={v!r} bad-char={ch!r}")

    # 3. report phrases for review
    if phrase:
        print("phrase rules:")
        for k, v in sorted(phrase.items()):
            print(f"  [{k}] -> [{v}]")

    print(f"\nwarnings: {len(warns)}")
    for w in warns[:50]:
        print("  WARN:", w)
    print(f"errors: {len(errors)}")
    for e in errors[:50]:
        print("  ERR :", e)

    # 4. optional corpus dry-run
    if args.corpus:
        phrase_sorted = sorted(phrase.items(), key=lambda kv: -len(kv[0]))
        table = str.maketrans(single)
        out_chars: Counter = Counter()
        phrase_hits: Counter = Counter()
        n_files = 0

        def iter_corpus_texts(path: str):
            p = Path(path)
            if p.is_dir():
                for f in sorted(p.rglob("*.json")):
                    try:
                        yield f.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
            else:
                z = zipfile.ZipFile(p)
                for n in z.namelist():
                    if not n.endswith(".json"):
                        continue
                    try:
                        yield z.read(n).decode("utf-8")
                    except UnicodeDecodeError:
                        continue

        for text in iter_corpus_texts(args.corpus):
            for k, v in phrase_sorted:
                c = text.count(k)
                if c:
                    phrase_hits[k] += c
                    text = text.replace(k, v)
            text = text.translate(table)
            out_chars.update(text)
            n_files += 1
        outside = {}
        for ch, c in out_chars.items():
            o = ord(ch)
            if o < 128 or is_hangul(ch):
                continue
            if ch not in safe:
                outside[ch] = c
        print(f"\ncorpus dry-run: files={n_files}")
        print(f"  phrase hits: {dict(phrase_hits.most_common())}")
        print(f"  chars outside safe (non-ASCII, non-Hangul): {len(outside)}")
        for ch, c in sorted(outside.items(), key=lambda kv: -kv[1])[:50]:
            print(f"    {ch!r}: {c}")
        if outside:
            errors.append(f"corpus dry-run: {len(outside)} chars outside safe charset")

    if errors:
        print("\nAUDIT FAILED", file=sys.stderr)
        sys.exit(1)
    print("\nAUDIT OK")

if __name__ == "__main__":
    main()
