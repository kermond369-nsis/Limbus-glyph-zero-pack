#!/usr/bin/env python3
"""Pack zero-assoc (LLC_zh-CN) localize into Android jp.zip with glyph map.

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
from pathlib import Path

GAME_PKG = "com.ProjectMoon.LimbusCompany"
LOCALIZE_REL = "files/Assets/Resources_moved/Localize"
DEFAULT_PREFIX = "JP_"


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def load_json_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k, v in (data.get("map") or {}).items():
        if len(k) == 1 and isinstance(v, str) and v:
            out[k] = v
    return out


def load_font_ok(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(path.read_text(encoding="utf-8").strip())


def apply_glyphs(text: str, mapping: dict[str, str], font_ok: set[str]) -> str:
    if not mapping:
        return text
    table = {ord(k): v for k, v in mapping.items()}
    converted = text.translate(table)
    # If mapping missed a char that is still not in font_ok, leave it
    # (CI map should be closed; app has runtime pool).
    _ = font_ok
    return converted


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


def build(input_path: Path, output: Path, glyph_map: Path, font_ok: Path, prefix: str) -> None:
    mapping = load_json_map(glyph_map)
    fonts = load_font_ok(font_ok)
    print(f"glyph_map={len(mapping)} font_ok={len(fonts)} input={input_path}")

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
            if src.suffix.lower() == ".json" and mapping:
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    dest.write_bytes(raw)
                else:
                    dest.write_bytes(apply_glyphs(text, mapping, fonts).encode("utf-8"))
            else:
                dest.write_bytes(raw)
            count += 1

        print(f"files_written={count}")
        if count < 100:
            die(f"suspiciously few files ({count}) — aborting")
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        out_base = td_path / "out"
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out_base.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(out_base).as_posix())
        digest = sha256_file(output)
        print(f"output={output} size={output.stat().st_size} sha256={digest}")
        if output.stat().st_size < 100_000:
            die(f"output too small ({output.stat().st_size} bytes)")
        Path(str(output) + ".sha256").write_text(
            f"{digest}  {output.name}\n", encoding="utf-8"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--output", "-o", default="jp.zip")
    ap.add_argument("--glyph-map", default="assets/glyph_map.json")
    ap.add_argument("--font-ok", default="assets/font_ok.txt")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    args = ap.parse_args()
    build(
        Path(args.input).resolve(),
        Path(args.output).resolve(),
        Path(args.glyph_map).resolve(),
        Path(args.font_ok).resolve(),
        args.prefix,
    )


if __name__ == "__main__":
    main()
