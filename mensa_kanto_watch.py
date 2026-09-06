#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAPAN MENSA 入会テスト日程ページの「関東地方」枠を監視し、
満員/締切 → 申込可 に変化したら通知するスクリプト。

使い方:
  1. 下の CONFIG を自分の通知先に合わせて書き換える
  2. `python3 mensa_kanto_watch.py` を cron / GitHub Actions などで
     数分おきに実行する（例: */3 * * * *）
  3. 初回実行時は state.json が無いので「現状把握」だけして終了する
     （いきなり全件通知が飛ばないようにするため）

このスクリプトは「一覧ページの空き枠検知→通知」までを行う。
実際の申込フォーム送信（顔写真アップロード・同意事項・支払い等が
絡む、取り消し不可な手続き）は安全のためここでは自動化しない。
通知が来たら自分でリンクを開いて申し込む運用を推奨する。
"""

import json
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ============ CONFIG ============
EXAM_URL = "https://mensa.jp/exam/"
STATE_FILE = Path(__file__).parent / "mensa_state.json"
TARGET_REGION = "関東地方"

# 通知方法。使わないものは空/Noneのままでよい。
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL") or None
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL") or None
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN") or None

# --- メール通知設定(環境変数 or GitHub Secretsから読む) ---
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
# =================================

STATUS_QUOTA = "満員"
STATUS_EXPIRE = "締切"
STATUS_OPEN = "申込可"


def fetch_html() -> str:
    resp = requests.get(EXAM_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; MensaWatcher/1.0)"
    })
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def parse_region_section(html: str, region_name: str) -> str:
    """指定地方の見出しから次の地方見出しまでのHTML断片を取り出す"""
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.find_all(["h2", "h3"])
    start = None
    for i, h in enumerate(headings):
        if region_name in h.get_text():
            start = h
            break
    if start is None:
        raise ValueError(f"見出し '{region_name}' が見つかりません(サイト構造が変わった可能性)")

    frag = []
    for sib in start.find_next_siblings():
        # 次の地方見出し(h2/h3)が出たら終了
        if sib.name in ("h2", "h3"):
            break
        frag.append(str(sib))
    return "".join(frag)


def extract_entries(region_html: str):
    """
    地方セクションHTMLから各テスト枠を抽出。
    ステータスは画像ファイル名(entry_quota / entry_expire / entry_out)で判定。
    """
    soup = BeautifulSoup(region_html, "html.parser")
    entries = []

    # 日時テキストを含むブロックを起点に、直後のステータス画像を探す
    for dt_text in soup.find_all(string=re.compile(r"日時\s*：")):
        block = dt_text.find_parent()
        if block is None:
            continue
        # ブロック以降の近傍からステータス画像/リンクを探す
        status = None
        link = None
        # 同じ親要素内、または次の要素をチェック
        search_scope = block.parent if block.parent else block
        img = search_scope.find("img", src=re.compile(r"entry_(quota|expire|out)\.jpg"))
        if img:
            src = img["src"]
            if "entry_quota" in src:
                status = STATUS_QUOTA
            elif "entry_expire" in src:
                status = STATUS_EXPIRE
            elif "entry_out" in src:
                status = STATUS_OPEN
                a = img.find_parent("a")
                if a and a.get("href"):
                    link = a["href"]

        entries.append({
            "datetime": dt_text.strip(),
            "status": status,
            "link": link,
        })
    return entries


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def notify(message: str):
    print(message)
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
    if SLACK_WEBHOOK_URL:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    if LINE_NOTIFY_TOKEN:
        requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"},
            data={"message": message},
            timeout=10,
        )
    if EMAIL_ENABLED:
        send_email(subject="【MENSA】関東地方の申込枠が開きました", body=message)


def send_email(subject: str, body: str):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    to_addrs = [addr.strip() for addr in EMAIL_TO.split(",")]
    msg["To"] = ", ".join(to_addrs)

    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, to_addrs, msg.as_string())


def main():
    if os.environ.get("TEST_NOTIFY", "false").lower() == "true":
        notify("🧪 これはMENSA関東監視スクリプトのテスト通知です。\n"
               "この文面が届いていれば、メール通知の設定は正しく動作しています。")
        print("テスト通知を送信しました。")
        return

    html = fetch_html()
    region_html = parse_region_section(html, TARGET_REGION)
    entries = extract_entries(region_html)

    if not entries:
        print("枠が見つかりませんでした。サイト構造の変更を確認してください。", file=sys.stderr)
        return

    old_state = load_state()
    new_state = {}
    newly_open = []

    for e in entries:
        key = e["datetime"]
        new_state[key] = e["status"]
        prev_status = old_state.get(key)
        if e["status"] == STATUS_OPEN and prev_status != STATUS_OPEN:
            newly_open.append(e)

    save_state(new_state)

    if not old_state:
        print("初回実行: 現状のみ記録しました。次回以降の変化を通知します。")
        for e in entries:
            print(f"  {e['datetime']}: {e['status']}")
        return

    if newly_open:
        lines = ["🎉 関東地方で新しい申込枠が開きました！"]
        for e in newly_open:
            url = e["link"] if e["link"] else EXAM_URL
            if url.startswith("/"):
                url = "https://mensa.jp" + url
            lines.append(f"・{e['datetime']} → {url}")
        notify("\n".join(lines))
    else:
        print("変化なし。")


if __name__ == "__main__":
    main()
