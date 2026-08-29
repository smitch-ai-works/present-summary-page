# -*- coding: utf-8 -*-
"""bonuses.json から index.html の const bonuses 配列を再生成する。

  python tools/build_hub.py           # 書き込む
  python tools/build_hub.py --check   # 差分の有無だけ見る（書き込まない・差分ありで終了コード1）

index.html のそれ以外の部分（CSS・著者カード・フッター）は一切触らない。
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import hub_data as D

ARRAY_RE = r"const\s+bonuses\s*=\s*\[.*?\];"


def render(doc):
    return "const bonuses = " + json.dumps(D.live_cards(doc), ensure_ascii=False) + ";"


def apply(html, doc):
    import re
    m = re.search(ARRAY_RE, html, re.S)
    if not m:
        raise SystemExit("index.html に const bonuses 配列が見つからない")
    return html[:m.start()] + render(doc) + html[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    doc = D.load()
    with open(D.HTML_PATH, encoding="utf-8") as f:
        old = f.read()
    new = apply(old, doc)

    cards = D.live_cards(doc)
    counts = {}
    for b in doc["bonuses"]:
        counts[b["status"]] = counts.get(b["status"], 0) + 1
    print("  " + " / ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"  掲載: {len(cards)}本")

    # 画像の実在チェック（落とすと全カードのアイキャッチが消える事故があった）
    import os
    missing = [c["image"] for c in cards
               if not os.path.exists(os.path.join(D.ROOT, c["image"]))]
    if missing:
        raise SystemExit("  画像が見つからない: " + ", ".join(missing))

    if new == old:
        print("  差分なし")
        return 0
    if args.check:
        print("  差分あり（--check なので書き込まない）")
        return 1
    with open(D.HTML_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("  index.html を更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
