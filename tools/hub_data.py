# -*- coding: utf-8 -*-
"""bonuses.json の読み書きと、掲載データの共通ロジック。

このリポジトリの掲載内容の唯一の真実は bonuses.json。
index.html は生成物なので、カードのデータを直接編集しないこと。
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "bonuses.json")
HTML_PATH = os.path.join(ROOT, "index.html")

STATUSES = ("draft", "scheduled", "live", "hidden")


def load(path=JSON_PATH):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    validate(doc)
    return doc


def save(doc, path=JSON_PATH):
    validate(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


LABELS = {"category": "カテゴリ", "title": "タイトル", "description": "説明文",
          "tags": "タグ", "image": "サムネ", "accent": "アクセント色"}


def validate(doc):
    """保存前のチェック。

    ページに出るもの（live / scheduled）だけ全項目を必須にする。
    draft / hidden は書きかけを保存できないと不便なので title と image だけ見る。
    """
    seen = set()
    for b in doc["bonuses"]:
        slug = b["slug"]
        if slug in seen:
            raise ValueError(f"slug が重複している: {slug}")
        seen.add(slug)
        if b["status"] not in STATUSES:
            raise ValueError(f"{slug}: 不正な status: {b['status']}")
        if b["status"] == "scheduled" and not b.get("publish_at"):
            raise ValueError(f"{slug}: 公開予約の日時が空です")

        keys = ("title", "image")
        if b["status"] in ("live", "scheduled"):
            keys = ("category", "title", "description", "tags", "image", "accent")
        for key in keys:
            if not b.get(key):
                tail = ("（ページに出すには全項目が必要です）"
                        if b["status"] in ("live", "scheduled") else "")
                raise ValueError(f"{slug}: {LABELS[key]}が空です{tail}")


def parse_at(s):
    """publish_at をJSTのdatetimeにする。タイムゾーン省略時はJSTとみなす。"""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def plain_title(title):
    return re.sub(r"<[^>]+>", " ", title).replace("  ", " ").strip()


def push(root=ROOT, message=None):
    """差分があれば commit して origin/main へ push する。差分がなければ何もしない。

    live / scheduled の状態変更をその場でGitHubに届けるための共通処理。
    差分があった場合は git status --short の出力を、無ければ None を返す。
    """
    r = subprocess.run(["git", "status", "--short"], cwd=root,
                        capture_output=True, text=True)
    if not r.stdout.strip():
        return None
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", message or "ハブページを更新"],
                    cwd=root, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=root, check=True)
    return r.stdout


def live_cards(doc):
    """index.html に出力する配列を組み立てる。

    status が "live" のものだけを、bonuses の並び順のまま出す。
    number は毎回 01 から振り直すので、差し替えても番号がズレない。
    """
    cards = []
    for b in doc["bonuses"]:
        if b["status"] != "live":
            continue
        cards.append({
            "number": f"{len(cards) + 1:02d}",
            "category": b["category"],
            "title": b["title"],
            "plainTitle": plain_title(b["title"]),
            "description": b["description"],
            "tags": b["tags"],
            "url": doc["base_url"] + b["slug"] + "/",
            "image": b["image"],
            "accent": b["accent"],
        })
    return cards
