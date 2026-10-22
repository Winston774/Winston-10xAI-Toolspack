#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["budoux>=0.6"]
# ///
"""deck-atelier · phrase.py — BudouX phrase boundaries for phrase.mjs.

    echo '{"lang": "zh-Hant-TW", "texts": ["拿掉循環，只留注意力"]}' | uv run scripts/phrase.py
    → {"model": "zh-hant", "breaks": [[2, 5, 7, 8]]}       拿掉|循環，|只留|注|意力

Each list holds the offsets where a new phrase starts, in UTF-16 code units so
phrase.mjs can index its JavaScript strings directly. BudouX alone splits some
words (注|意力 above), so phrase.mjs keeps only the breaks that also fall on a word
boundary (Intl.Segmenter) and turns them into <wbr>; this script never sees or
writes HTML.
"""
import json
import sys

import budoux


def pick(lang):
    tag = (lang or "").lower().replace("_", "-")
    if tag.startswith("ja"):
        return "ja", budoux.load_default_japanese_parser()
    if tag.startswith("zh") and any(k in tag for k in ("hans", "-cn", "-sg", "-my")):
        return "zh-hans", budoux.load_default_simplified_chinese_parser()
    return "zh-hant", budoux.load_default_traditional_chinese_parser()


def utf16(s):
    return len(s.encode("utf-16-le")) // 2


def main():
    req = json.load(sys.stdin)
    model, parser = pick(req.get("lang"))
    out = []
    for text in req.get("texts", []):
        breaks, at = [], 0
        for chunk in parser.parse(text)[:-1]:
            at += utf16(chunk)
            breaks.append(at)
        out.append(breaks)
    json.dump({"model": model, "breaks": out}, sys.stdout)


if __name__ == "__main__":
    main()
