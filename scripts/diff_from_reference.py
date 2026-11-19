#!/usr/bin/env python3
"""Incremental diff tool comparing 零协 source against reference localization.

Dry-runs the current glyph map over a 零协 corpus (.zip or directory), compares any
characters still outside safe_charset against a reference release (such as
ghcruise/LimbusCompany-IOS-Localization's localize_jp.zip), and classifies each
into KEEP_SAFE, REPLACE_SINGLE, or MANUAL_REVIEW.

Usage:
  python3 scripts/diff_from_reference.py \
    --llc /path/to/LimbusLocalize.zip \
    --ref /path/to/localize_jp.zip

  # Apply unambiguous KEEP_SAFE and REPLACE_SINGLE updates in-place:
  python3 scripts/diff_from_reference.py \
    --llc /path/to/LimbusLocalize.zip \
    --ref /path/to/localize_jp.zip \
    --apply --new-version 2026-11-20.full9
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP = ROOT / "assets/glyph_map.json"
DEFAULT_SAFE = ROOT / "assets/safe_charset.txt"
TAG_RE = re.compile(r"<[^>]+>")


def is_hangul(ch: str) -> bool:
    o = ord(ch)
    return (0xAC00 <= o <= 0xD7AF) or (0x1100 <= o <= 0x11FF) or (0x3130 <= o <= 0x318F)


def normalize_filename(path_str: str) -> str:
    """Strip directory prefixes and JP_/KR_ filename prefix for alignment."""
    base = path_str.replace("\\", "/").rsplit("/", 1)[-1]
    if base.startswith(("JP_", "KR_")):
        return base[3:]
    return base


def load_corpus_jsons(path: Path) -> dict[str, str]:
    """Load all UTF-8 JSON texts from a .zip archive or directory keyed by base name."""
    out: dict[str, str] = {}
    if path.is_dir():
        for f in sorted(path.rglob("*.json")):
            try:
                out[normalize_filename(f.name)] = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        return out
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".json"):
                continue
            try:
                out[normalize_filename(name)] = zf.read(name).decode("utf-8")
            except UnicodeDecodeError:
                continue
    return out


def iter_json_strings(obj: object, prefix: str = ""):
    """Yield (path, string_value) pairs, keying list items by 'id' when present."""
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_json_strings(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            if isinstance(item, dict) and "id" in item:
                yield from iter_json_strings(item, f"{prefix}[id={item['id']}]")
            else:
                yield from iter_json_strings(item, f"{prefix}[{idx}]")


def find_outside_chars(
    llc: dict[str, str],
    single: dict[str, str],
    phrases: list[tuple[str, str]],
    safe: set[str],
) -> tuple[Counter, dict[str, list[tuple[str, str]]]]:
    """Dry-run current map over LLC corpus and return outside-safe char counts & snippets."""
    table = str.maketrans(single)
    outside: Counter = Counter()
    examples: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for base, raw in llc.items():
        text = raw
        for k, v in phrases:
            if k in text:
                text = text.replace(k, v)
        text = text.translate(table)
        for ch in set(text):
            if ord(ch) < 128 or is_hangul(ch) or ch in safe:
                continue
            outside[ch] += text.count(ch)
            if len(examples[ch]) < 3:
                idx = raw.find(ch)
                if idx == -1:
                    idx = text.find(ch)
                snippet = raw[max(0, idx - 16) : idx + 17].replace("\n", " ")
                examples[ch].append((base, snippet))
    return outside, examples


def collect_transitions(
    llc: dict[str, str],
    ref: dict[str, str],
    outside_chars: set[str],
) -> tuple[dict[str, Counter], dict[str, Counter]]:
    """Align shared JSON fields and count char/phrase transitions for outside chars."""
    single_trans: dict[str, Counter] = defaultdict(Counter)
    non_eq_trans: dict[str, Counter] = defaultdict(Counter)

    for base in sorted(set(llc) & set(ref)):
        raw_l = llc[base]
        if not any(ch in raw_l for ch in outside_chars):
            continue
        try:
            jl = json.loads(raw_l)
            jr = json.loads(ref[base])
        except json.JSONDecodeError:
            continue
        ml = dict(iter_json_strings(jl))
        mr = dict(iter_json_strings(jr))
        for path, sl in ml.items():
            if path not in mr:
                continue
            sl_clean = TAG_RE.sub("", sl)
            if not any(ch in sl_clean for ch in outside_chars):
                continue
            sr_clean = TAG_RE.sub("", mr[path])
            if len(sl_clean) == len(sr_clean):
                for a, b in zip(sl_clean, sr_clean):
                    if a in outside_chars:
                        single_trans[a][b] += 1
            else:
                sm = difflib.SequenceMatcher(None, sl_clean, sr_clean)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    src_seg = sl_clean[i1:i2]
                    tgt_seg = sr_clean[j1:j2]
                    if not any(ch in src_seg for ch in outside_chars):
                        continue
                    if tag == "equal":
                        for a in src_seg:
                            if a in outside_chars:
                                single_trans[a][a] += 1
                    elif tag == "replace" and len(src_seg) == len(tgt_seg):
                        for a, b in zip(src_seg, tgt_seg):
                            if a in outside_chars:
                                single_trans[a][b] += 1
                    else:
                        for ch in outside_chars:
                            if ch in src_seg:
                                non_eq_trans[ch][(src_seg[:24], tgt_seg[:24])] += 1
    return single_trans, non_eq_trans


def classify_outside_chars(
    outside: Counter,
    ref_chars: set[str],
    single_trans: dict[str, Counter],
    non_eq_trans: dict[str, Counter],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Split outside chars into KEEP_SAFE, REPLACE_SINGLE, and MANUAL_REVIEW."""
    keep_safe: list[str] = []
    replace_single: dict[str, str] = {}
    manual_review: list[str] = []

    for ch, _ in outside.most_common():
        if unicodedata.category(ch) == "Cf":
            manual_review.append(ch)
            continue
        trans = single_trans.get(ch)
        if not trans:
            manual_review.append(ch)
            continue
        total = sum(trans.values())
        best_tgt, best_cnt = trans.most_common(1)[0]
        if best_cnt / total < 0.9 or (len(trans) > 1 and total < 5):
            manual_review.append(ch)
            continue
        if best_tgt == ch and ch in ref_chars and not non_eq_trans.get(ch):
            keep_safe.append(ch)
        elif best_tgt != ch and (best_tgt in ref_chars or ord(best_tgt) < 128):
            replace_single[ch] = best_tgt
        else:
            manual_review.append(ch)
    return keep_safe, replace_single, manual_review


def apply_updates(
    map_path: Path,
    safe_path: Path,
    gm_data: dict,
    safe_set: set[str],
    keep_safe: list[str],
    replace_single: dict[str, str],
    new_version: str,
) -> None:
    """Write unambiguous KEEP_SAFE and REPLACE_SINGLE additions back to assets."""
    changed_map = False
    for src, tgt in replace_single.items():
        if src not in gm_data["map"]:
            gm_data["map"][src] = tgt
            changed_map = True
        if ord(tgt) >= 128 and not is_hangul(tgt):
            safe_set.add(tgt)

    for ch in keep_safe:
        safe_set.add(ch)

    if new_version:
        gm_data["version"] = new_version
        changed_map = True

    if changed_map:
        text = json.dumps(gm_data, ensure_ascii=False, indent=2) + "\n"
        map_path.write_bytes(text.encode("utf-8"))

    merged = "".join(sorted(safe_set))
    if not merged.endswith("\n"):
        merged += "\n"
    safe_path.write_bytes(merged.encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Diff 零协 corpus against reference localization")
    ap.add_argument("--llc", required=True, help="Path to 零协 LimbusLocalize archive (.zip) or dir")
    ap.add_argument("--ref", required=True, help="Path to reference localize_jp.zip or dir")
    ap.add_argument("--map", default=str(DEFAULT_MAP))
    ap.add_argument("--safe-charset", default=str(DEFAULT_SAFE))
    ap.add_argument("--apply", action="store_true", help="Apply KEEP_SAFE and REPLACE_SINGLE updates")
    ap.add_argument("--new-version", default="", help="Optional glyph_map version when using --apply")
    args = ap.parse_args()

    map_path = Path(args.map)
    safe_path = Path(args.safe_charset)
    gm_data = json.loads(map_path.read_text(encoding="utf-8"))
    raw_map: dict[str, str] = gm_data.get("map") or {}
    safe_set = set(safe_path.read_text(encoding="utf-8"))

    single = {k: v for k, v in raw_map.items() if len(k) == 1}
    phrases = sorted(((k, v) for k, v in raw_map.items() if len(k) > 1), key=lambda kv: -len(kv[0]))

    llc = load_corpus_jsons(Path(args.llc))
    ref = load_corpus_jsons(Path(args.ref))
    print(f"Loaded LLC={len(llc)} JSON files, REF={len(ref)} JSON files, shared={len(set(llc) & set(ref))}")

    outside, examples = find_outside_chars(llc, single, phrases, safe_set)
    print(f"Outside safe_charset characters remaining: {len(outside)}")
    if not outside:
        return

    ref_chars: set[str] = set()
    for raw in ref.values():
        ref_chars.update(TAG_RE.sub("", raw))

    single_trans, non_eq_trans = collect_transitions(llc, ref, set(outside))
    keep_safe, replace_single, manual_review = classify_outside_chars(
        outside, ref_chars, single_trans, non_eq_trans
    )

    print(f"\n[KEEP_SAFE] ({len(keep_safe)} chars)")
    for ch in keep_safe:
        print(f"  U+{ord(ch):04X} {ch!r} (llc_cnt={outside[ch]})")

    print(f"\n[REPLACE_SINGLE] ({len(replace_single)} mappings)")
    for src, tgt in replace_single.items():
        in_safe = tgt in safe_set
        print(f"  U+{ord(src):04X} {src!r} -> {tgt!r} (llc_cnt={outside[src]}, tgt_in_safe={in_safe})")

    print(f"\n[MANUAL_REVIEW] ({len(manual_review)} chars)")
    for ch in manual_review:
        hint = "strip suggested (-> '')" if unicodedata.category(ch) == "Cf" else ""
        trans = dict(single_trans[ch].most_common(5))
        neq = dict(non_eq_trans[ch].most_common(2))
        print(f"  U+{ord(ch):04X} {ch!r} cnt={outside[ch]} {hint} | single={trans} | non_eq={neq} | ex={examples[ch][:2]}")

    if args.apply:
        apply_updates(map_path, safe_path, gm_data, safe_set, keep_safe, replace_single, args.new_version)
        print(f"\nApplied {len(keep_safe)} KEEP_SAFE + {len(replace_single)} REPLACE_SINGLE updates.")


if __name__ == "__main__":
    main()
