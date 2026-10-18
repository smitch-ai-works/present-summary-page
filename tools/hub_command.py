# -*- coding: utf-8 -*-
"""管理ページ（admin.html）から送られた操作を bonuses.json に反映する。

  python tools/hub_command.py <イベントJSON or 本文テキスト> <結果の書き出し先>

GitHub Actions（hub-command.yml）が、リポジトリ所有者の立てた
「[まとめ操作]」Issue の本文を渡して呼ぶ。本文は次の形：

    action: schedule        # schedule（日時を指定）/ now（今すぐ）/ cancel（予約をやめる）
                            # archive（アーカイブにしまう）/ unarchive（アーカイブから戻す）
    slug: no40-ai-motion-video
    publish_at: 2026-10-20T18:00   # 日本時間。schedule のときだけ
    number: 29                     # 掲載番号。省略時は今の位置（未掲載なら末尾）

結果（成功・失敗とも）を日本語で書き出し、Issue へのコメントに使う。
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hub_data as D

ACTIONS = ("schedule", "now", "cancel", "archive", "unarchive")


def parse(body):
    fields = {}
    for line in body.splitlines():
        m = re.match(r"^\s*(action|slug|publish_at|number)\s*:\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    if fields.get("action") not in ACTIONS:
        raise ValueError("操作の種類（action）が読めませんでした。管理ページからもう一度送ってください")
    if not fields.get("slug"):
        raise ValueError("どの特典か（slug）が読めませんでした")
    return fields


def lp_is_up(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def apply(doc, f, now):
    """doc を書き換え、Issueに返す報告の行リストを返す。"""
    b = next((x for x in doc["bonuses"] if x["slug"] == f["slug"]), None)
    if b is None:
        raise ValueError(f"{f['slug']} は bonuses.json にありません")
    name = D.plain_title(b["title"])
    action = f["action"]

    if action == "cancel":
        if b["status"] != "scheduled":
            raise ValueError(f"{name} は予約中ではありません（いまの状態：{b['status']}）")
        b["status"] = "draft"
        b["publish_at"] = None
        return [f"「{name}」の公開予約を取り消しました。下書きに戻っています。"]

    if action == "archive":
        if b["status"] == "live":
            raise ValueError(f"{name} は公開中です。公開中の特典はアーカイブにできません")
        if b.get("archived"):
            raise ValueError(f"{name} はもうアーカイブに入っています")
        was_scheduled = b["status"] == "scheduled"
        if was_scheduled:
            b["status"] = "draft"
            b["publish_at"] = None
        b["archived"] = True
        return [f"「{name}」をアーカイブにしまいました。" + ("公開予約も取り消しています。" if was_scheduled else ""),
                "管理ページの「アーカイブ」からいつでも戻せます。"]

    if action == "unarchive":
        if not b.pop("archived", False):
            raise ValueError(f"{name} はアーカイブに入っていません")
        return [f"「{name}」をアーカイブから戻しました。管理ページの「出せる」か「準備中」に並びます。"]

    if b["status"] == "hidden":
        raise ValueError(f"{name} は非表示にした特典です。出し直すときはClaudeに頼んでください")
    if action == "schedule" and b["status"] == "live":
        raise ValueError(f"{name} はもう公開中です")

    number = f.get("number", "").strip()
    if number:
        if not number.isdigit() or int(number) < 1:
            raise ValueError(f"掲載番号は1以上の数字にしてください（受け取った値：{number}）")
        D.move_to_number(doc, b, int(number))
    elif not D.shown(b):
        D.move_to_number(doc, b, 10 ** 6)

    b.pop("archived", None)  # アーカイブから直接出すときは取り出したことにする
    if action == "now":
        b["status"] = "live"
        b["publish_at"] = now.isoformat(timespec="seconds")
    else:
        at = f.get("publish_at", "").strip()
        if not at:
            raise ValueError("公開日時が空です")
        try:
            at = D.parse_at(at)
        except ValueError:
            raise ValueError(f"公開日時が読めませんでした（受け取った値：{f['publish_at']}）")
        b["status"] = "scheduled"
        b["publish_at"] = at.isoformat(timespec="seconds")

    order = [x for x in doc["bonuses"] if D.shown(x)]
    pos = order.index(b) + 1
    lines = []
    if action == "now":
        lines.append(f"「{name}」を **特典{pos:02d}** として今すぐ公開します。1〜2分でまとめページに出ます。")
    else:
        at = D.parse_at(b["publish_at"])
        lines.append(f"「{name}」を **{at.month}/{at.day} {at:%H:%M}（日本時間）** に **特典{pos:02d}** として出す予約をしました。"
                     "その時刻ちょうどにまとめページへ表示されます。")
    after = order[pos:]
    if after:
        shifted = "、".join(D.plain_title(x["title"]) for x in after[:3]) + (" ほか" if len(after) > 3 else "")
        lines.append(f"⚠ 後ろの{len(after)}本（{shifted}）の番号が1つずつ後ろにずれます。DMなどで番号を案内している場合は直してください。")
    url = doc["base_url"] + b["slug"] + "/"
    if not lp_is_up(url):
        lines.append(f"⚠ 特典ページ {url} がまだ開けません。公開時刻までに特典ページ側の公開が必要です。")
    return lines


def read_body(src):
    if src.endswith(".json"):
        with open(src, encoding="utf-8") as fp:
            return json.load(fp)["issue"]["body"] or ""
    with open(src, encoding="utf-8") as fp:
        return fp.read()


def main():
    src, out = sys.argv[1], sys.argv[2]
    ok = True
    try:
        doc = D.load()
        lines = apply(doc, parse(read_body(src)), datetime.now(D.JST))
        D.save(doc)
    except ValueError as e:
        ok = False
        lines = [f"❌ 反映できませんでした：{e}", "", "まとめページは何も変わっていません。"]
    text = "\n\n".join(lines)
    print(text)
    with open(out, "w", encoding="utf-8") as fp:
        fp.write(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
