#!/usr/bin/env python3
"""
translation_report.py

Scans a repository folder (default: product_catalog) for product.json files,
searches JSON structures for objects/arrays containing 'en'/'de' language keys,
and emits a JSON report listing problems:
 - missing_de: kein "de" Feld
 - empty_de: "de" ist leer
 - identical_en_de: "de" == "en"
 - de_contains_english: heuristische Erkennung von englischen Wörtern in "de"

Usage:
  python translation_report.py --root /path/to/repo --out report.json
  python translation_report.py --root . --out report.json --fix-copy-en  # optional
"""
import argparse
import json
import os
import re
from collections import defaultdict

# Small list of indicative English words (expandable)
EN_WORDS = {
    "the","and","or","model","version","real-time","real", "time", "data",
    "battery","charge","power","voltage","current","inverter","meter",
    "status","manufacturer","firmware","serial","number","max","min","today",
    "kwh","kw","w","phase","input","output","module","state","mode"
}

WORD_RE = re.compile(r"[A-Za-z\-']{2,}")

def find_product_json_files(root):
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower() == "product.json":
                matches.append(os.path.join(dirpath, fn))
    return matches

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception as e:
            print(f"ERROR parsing JSON {path}: {e}")
            return None

def iter_language_objects(obj, path=()):
    """
    Recursively yield (container, key, value, json_path) for any dict that:
     - has 'en' or 'de' keys (common case), OR
     - is a list of dicts where elements have 'en'/'de' keys.
    json_path is a tuple of keys/indices to reach the object.
    """
    if isinstance(obj, dict):
        # direct language object
        if 'en' in obj or 'de' in obj:
            yield (obj, None, obj, path)
        # also check nested dicts
        for k, v in obj.items():
            for item in iter_language_objects(v, path + (k,)):
                yield item
    elif isinstance(obj, list):
        # if this list contains dict elements with en/de, treat each element
        contains_lang = any(isinstance(el, dict) and ('en' in el or 'de' in el) for el in obj)
        if contains_lang:
            for idx, el in enumerate(obj):
                if isinstance(el, dict):
                    if 'en' in el or 'de' in el:
                        yield (obj, idx, el, path + (idx,))
                    # also look deeper inside element
                    for item in iter_language_objects(el, path + (idx,)):
                        yield item
        else:
            # generic recursion
            for idx, el in enumerate(obj):
                for item in iter_language_objects(el, path + (idx,)):
                    yield item

def count_english_indicators(text):
    if not isinstance(text, str) or not text.strip():
        return 0, 0
    words = WORD_RE.findall(text)
    if not words:
        return 0, 0
    words_lower = [w.lower() for w in words]
    hits = sum(1 for w in words_lower if w in EN_WORDS)
    return hits, len(words_lower)

def analyze_file(path, root):
    data = load_json(path)
    if data is None:
        return {"error": "json_parse_error"}
    issues = []
    for container, key, obj, jpath in iter_language_objects(data):
        # obj is the dict that contains 'en'/'de' or similar
        en = obj.get('en')
        de = obj.get('de')
        issue = {"json_path": "/".join(map(str, jpath))}
        found_any = False
        if en is None and de is None:
            continue
        found_any = True
        if de is None:
            issue["problem"] = issue.get("problem", []) + ["missing_de"]
        else:
            # empty check
            if (isinstance(de, str) and not de.strip()) or (de == [] or de == {}):
                issue["problem"] = issue.get("problem", []) + ["empty_de"]
        if en is not None and de is not None:
            # identical check (stringified)
            try:
                if isinstance(en, str) and isinstance(de, str) and en.strip() and en.strip() == de.strip():
                    issue["problem"] = issue.get("problem", []) + ["identical_en_de"]
            except Exception:
                pass
            # heuristic english detection on de (only if de is string)
            if isinstance(de, str) and de.strip():
                hits, total = count_english_indicators(de)
                if total > 0 and (hits / total) >= 0.25:
                    # 25% of words are english indicators -> flag
                    issue["problem"] = issue.get("problem", []) + ["de_contains_english"]
                    issue["english_indicator_hits"] = hits
                    issue["english_indicator_total"] = total
        if found_any:
            # include sample values for context (trim long strings)
            def sample(x):
                if isinstance(x, str):
                    s = x.strip()
                    return s if len(s) <= 200 else s[:200] + "..."
                return x
            issue["sample_en"] = sample(en)
            issue["sample_de"] = sample(de)
            issues.append(issue)
    relpath = os.path.relpath(path, root)
    return {"path": relpath, "issues": issues}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="product_catalog", help="Root folder to scan (default: product_catalog)")
    p.add_argument("--out", default="translation_report.json", help="Output JSON report path")
    p.add_argument("--fix-copy-en", action="store_true",
                   help="If set, for missing/empty de fields the script will copy en->de and overwrite the file (use with caution)")
    args = p.parse_args()

    files = find_product_json_files(args.root)
    report = {"scanned_files_count": len(files), "results": []}
    for f in sorted(files):
        res = analyze_file(f, args.root)
        if "error" in res:
            report["results"].append({"path": os.path.relpath(f, args.root), "error": res["error"]})
            continue
        if res.get("issues"):
            report["results"].append(res)
            if args.fix_copy_en:
                # load, modify, and save file if we can
                data = load_json(f)
                modified = False
                # apply same traversal to write en->de where missing/empty
                for container, key, obj, jpath in iter_language_objects(data):
                    en = obj.get("en")
                    de = obj.get("de")
                    if en is not None and (de is None or (isinstance(de, str) and not de.strip())):
                        obj["de"] = en
                        modified = True
                if modified:
                    with open(f, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, ensure_ascii=False, indent=2)
        # small progress
    with open(args.out, "w", encoding="utf-8") as outf:
        json.dump(report, outf, ensure_ascii=False, indent=2)
    print(f"Wrote report to {args.out} (scanned {len(files)} product.json files)")

if __name__ == "__main__":
    main()
