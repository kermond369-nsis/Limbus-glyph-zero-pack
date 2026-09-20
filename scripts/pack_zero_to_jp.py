#!/usr/bin/env python3
"""Pack zero-assoc (LLC_zh-CN) localize into Android jp.zip with glyph map.

v2 pipeline (2026-09-21):
  - glyph_map.json may contain single-char entries AND phrase entries (len(key) > 1).
    Phrase rules are applied first (longest key first), then single chars via str.translate.
  - Closure check: every character in the OUTPUT must be inside assets/safe_charset.txt.
    Any char outside => error (fail-fast) unless --allow-outside is given.
  - Emits glyph-report.json next to the output with replacement statistics.

No secrets. Deterministic. Used locally and by GitHub Actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

GAME_PKG = "com.ProjectMoon.LimbusCompany"
LOCALIZE_REL = "files/Assets/Resources_moved/Localize"
DEFAULT_PREFIX = "JP_"


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


class GlyphMap:
    """Loaded glyph map: single-char table + phrase list (longest-first)."""

    def __init__(self, raw: dict[str, str], version: str = ""):
        self.version = version
        self.single: dict[str, str] = {}
        self.phrases: list[tuple[str, str]] = []
        for k, v in raw.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            if len(k) == 1:
                self.single[k] = v
            elif len(k) > 1:
                self.phrases.append((k, v))
        self.phrases.sort(key=lambda kv: -len(kv[0]))
        self._table = str.maketrans(self.single)

    def apply(self, text: str, stats: "GlyphStats") -> str:
        for k, v in self.phrases:
            n = text.count(k)
            if n:
                stats.phrase_hits[k] += n
                text = text.replace(k, v)
        cnt = Counter(text)
        for src in self.single:
            n = cnt.get(src, 0)
            if n:
                stats.single_hits[src] += n
        return text.translate(self._table)


class GlyphStats:
    def __init__(self) -> None:
        self.single_hits: Counter = Counter()
        self.phrase_hits: Counter = Counter()
        self.out_chars: Counter = Counter()
        self.files = 0

    def report(self, glyph_map: GlyphMap, safe: set[str], input_path: str) -> dict:
        outside = {}
        exempt = {"ascii": [0, 0], "hangul": [0, 0]}  # [char types, occurrences]
        for ch, c in self.out_chars.items():
            o = ord(ch)
            if o < 128:
                exempt["ascii"][0] += 1
                exempt["ascii"][1] += c
                continue
            # Hangul: game is natively Korean; JP-slot font chain covers Hangul.
            if (0xAC00 <= o <= 0xD7AF) or (0x1100 <= o <= 0x11FF) or (0x3130 <= o <= 0x318F):
                exempt["hangul"][0] += 1
                exempt["hangul"][1] += c
                continue
            if ch not in safe:
                outside[ch] = c
        rep = {
            "glyph_map_version": glyph_map.version,
            "input": input_path,
            "files": self.files,
            "entries": {"single": len(glyph_map.single), "phrase": len(glyph_map.phrases)},
            "single_hits_total": sum(self.single_hits.values()),
            "phrase_hits": dict(self.phrase_hits.most_common()),
            "top_single": [[s, glyph_map.single[s], c] for s, c in self.single_hits.most_common(50)],
            "chars_out_total": len(self.out_chars),
            "exempt_ascii": {"types": exempt["ascii"][0], "occ": exempt["ascii"][1]},
            "exempt_hangul": {"types": exempt["hangul"][0], "occ": exempt["hangul"][1]},
            "outside_safe_charset": dict(sorted(outside.items(), key=lambda kv: -kv[1])),
        }
        return rep


def load_glyph_map(path: Path) -> GlyphMap:
    if not path.exists():
        die(f"glyph map not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return GlyphMap(data.get("map") or {}, str(data.get("version") or ""))


def load_safe_charset(path: Path) -> set[str]:
    if not path.exists():
        die(f"safe charset not found: {path}")
    return set(path.read_text(encoding="utf-8"))


def extract_archive(src: Path, dest: Path) -> Path:
    """Return a directory that contains the localize tree."""
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        # Already extracted (CI case): use as-is, do NOT copy into empty dest.
        return src
    suf = src.suffix.lower()
    if suf == ".zip":
        with zipfile.ZipFile(src) as zf:
            zf.extractall(dest)
        return dest
    if suf in (".7z", ".rar"):
        if not shutil.which("7z"):
            die("need 7z binary to extract 7z/rar")
        subprocess.check_call(["7z", "x", f"-o{dest}", "-y", str(src)])
        return dest
    die(f"unsupported input type: {src}")


def find_content_root(root: Path) -> Path:
    if any(root.rglob("LLC_zh-CN")):
        cands = [p for p in root.rglob("LLC_zh-CN") if p.is_dir()]
        for c in sorted(cands, key=lambda p: len(p.parts)):
            if any(c.glob("*.json")):
                return c
    if any(root.glob("*.json")):
        return root
    best = None
    best_n = -1
    for p in [root, *root.rglob("*")]:
        if not p.is_dir():
            continue
        n = len(list(p.glob("*.json")))
        if n > best_n:
            best_n = n
            best = p
    if best is None or best_n <= 0:
        die(f"no *.json found under {root}")
    return best


def ensure_prefix(name: str, prefix: str) -> str:
    if name.startswith(prefix):
        return name
    if name.startswith("KR_"):
        return prefix + name[3:]
    return prefix + name


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(input_path: Path, output: Path, glyph_map: Path, safe_charset: Path,
          prefix: str, allow_outside: bool) -> None:
    gm = load_glyph_map(glyph_map)
    safe = load_safe_charset(safe_charset)
    stats = GlyphStats()
    print(f"glyph_map={gm.version} single={len(gm.single)} phrase={len(gm.phrases)} "
          f"safe_charset={len(safe)} input={input_path}")

    with tempfile.TemporaryDirectory(prefix="glyph_pack_") as td:
        td_path = Path(td)
        work = extract_archive(input_path, td_path / "in")
        content = find_content_root(work)
        print(f"content_root={content}")
        n_json = len(list(content.rglob("*.json")))
        print(f"json_under_root={n_json}")
        if n_json <= 0:
            die(f"content_root has no json files: {content}")

        out_root = td_path / "out" / "Android" / "data" / GAME_PKG / LOCALIZE_REL / "jp"
        out_root.mkdir(parents=True, exist_ok=True)
        count = 0
        for src in content.rglob("*"):
            if not src.is_file():
                continue
            if src.name.startswith(".") or src.name == "version.txt":
                continue
            rel = src.relative_to(content)
            parts = list(rel.parts)
            parts[-1] = ensure_prefix(parts[-1], prefix)
            dest = out_root.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            raw = src.read_bytes()
            if src.suffix.lower() == ".json":
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    dest.write_bytes(raw)
                else:
                    converted = gm.apply(text, stats)
                    stats.out_chars.update(converted)
                    dest.write_bytes(converted.encode("utf-8"))
            else:
                dest.write_bytes(raw)
            stats.files += 1
            count += 1

        print(f"files_written={count}")
        if count < 100:
            die(f"suspiciously few files ({count}) — aborting")

        rep = stats.report(gm, safe, str(input_path))
        outside = rep["outside_safe_charset"]
        if outside:
            top = list(outside.items())[:30]
            print(f"!! outside safe charset: {len(outside)} chars, top: {top}", file=sys.stderr)
            if not allow_outside:
                die("closure check failed: output contains chars outside safe charset")
            print("!! continuing because --allow-outside", file=sys.stderr)

        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        out_base = td_path / "out"
        # Deterministic zip: fixed timestamp so identical input => identical bytes/sha256.
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out_base.rglob("*")):
                if p.is_file():
                    arcname = p.relative_to(out_base).as_posix()
                    zi = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = 0o644 << 16
                    zf.writestr(zi, p.read_bytes())
        digest = sha256_file(output)
        print(f"output={output} size={output.stat().st_size} sha256={digest}")
        if output.stat().st_size < 100_000:
            die(f"output too small ({output.stat().st_size} bytes)")
        Path(str(output) + ".sha256").write_text(
            f"{digest}  {output.name}\n", encoding="utf-8"
        )

        rep["output"] = output.name
        rep["output_size"] = output.stat().st_size
        rep["output_sha256"] = digest
        report_path = Path(str(output) + ".report.json")
        report_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report={report_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--output", "-o", default="jp.zip")
    ap.add_argument("--glyph-map", default="assets/glyph_map.json")
    ap.add_argument("--safe-charset", default="assets/safe_charset.txt")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    ap.add_argument("--allow-outside", action="store_true",
                    help="downgrade closure-check failure to a warning")
    args = ap.parse_args()
    build(
        Path(args.input).resolve(),
        Path(args.output).resolve(),
        Path(args.glyph_map).resolve(),
        Path(args.safe_charset).resolve(),
        args.prefix,
        args.allow_outside,
    )


if __name__ == "__main__":
    main()
