# Translation Report Script

This folder contains a small Python script to scan product.json files under `product_catalog`
and detect missing or incorrect German (`de`) translations.

Files added:
- scripts/translation_report.py — the scanner script.

Usage (from repository root):

- Run without modifying files, write report to translation_report.json:

  python3 scripts/translation_report.py --root product_catalog --out translation_report.json

- To also create placeholder translations by copying `en` -> `de` where `de` is missing or empty (NOT a real translation):

  python3 scripts/translation_report.py --root product_catalog --out translation_report.json --fix-copy-en

Notes:
- The script uses a simple heuristic to detect English words in German translations; it may produce false positives.
- Recommended workflow: run the script, review `translation_report.json`, then create translation tasks or fix files manually.
