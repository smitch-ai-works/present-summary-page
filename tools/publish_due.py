# -*- coding: utf-8 -*-
"""公開予定時刻を過ぎた特典を live にする。

  python tools/publish_due.py

status が "scheduled" かつ publish_at <= 現在時刻(JST) のものだけを "live" に変える。
該当なしなら何も書き換えない（冪等）。GitHub Actions から毎時呼ばれる。
"""
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_data as D


def main():
    doc = D.load()
    now = datetime.now(D.JST)
    promoted = []

    for b in doc["bonuses"]:
        if b["status"] != "scheduled":
            continue
        if D.parse_at(b["publish_at"]) <= now:
            b["status"] = "live"
            promoted.append(b)

    if not promoted:
        print("  公開予定に達したものはなし")
        return

    D.save(doc)
    total = sum(1 for b in doc["bonuses"] if b["status"] == "live")
    for b in promoted:
        print(f"  公開: {b['slug']}（{D.plain_title(b['title'])}）")
    print(f"  掲載本数: {total}本")

    # コミットメッセージをワークフローへ渡す
    first = promoted[0]
    no = first["slug"].split("-")[0].replace("no", "")
    msg = f"特典{no}（{D.plain_title(first['title'])}）をハブページに追加（{total}本目）"
    if len(promoted) > 1:
        msg = f"特典{len(promoted)}本をハブページに追加（計{total}本）"
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"promoted=true\n")
            f.write(f"message={msg}\n")
    print(f"  message: {msg}")


if __name__ == "__main__":
    main()
