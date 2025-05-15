import os
import time
import smtplib
import requests
import json
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase 初期化 ---
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 環境変数 ---
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- JST 設定 ---
JST = timezone(timedelta(hours=9))

# --- Firestore から通知履歴を読み込み ---
def load_notified_counts():
    doc = db.collection("discogs").document("notified_counts").get()
    if doc.exists:
        return doc.to_dict()
    return {}

# --- Firestore に通知履歴を保存 ---
def save_notified_counts(data):
    db.collection("discogs").document("notified_counts").set(data)

# --- Wantlist のリリース情報取得 ---
def get_wantlist_items():
    items = []
    page = 1
    while True:
        url = f'https://api.discogs.com/users/{USER_NAME}/wants?page={page}&per_page=100'
        headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print("❌ Wantlist取得に失敗しました", resp.status_code)
            break
        wants = resp.json().get('wants', [])
        if not wants:
            break
        for w in wants:
            info = w['basic_information']
            rid = info['id']
            title = info['title']
            artists = ', '.join(a['name'] for a in info.get('artists', []))
            uri = f"https://www.discogs.com/release/{rid}"
            items.append({'release_id': rid, 'title': title, 'artist': artists, 'uri': uri})
        if len(wants) < 100:
            break
        page += 1
    return items

# --- リリースごとの出品数取得（リトライ付き） ---
def get_num_for_sale(release_id, retries=3):
    url = f'https://api.discogs.com/releases/{release_id}'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    for i in range(retries):
        r = requests.get(url, headers=headers)
        print(f"🔍 Checking release_id: {release_id}")
        print(f"📦 API Response: {r.status_code}")
        if r.status_code == 200:
            return r.json().get('num_for_sale', 0)
        if r.status_code == 429:
            print("⚠️ 429エラー、5秒待って再試行...")
            time.sleep(5)
            continue
        print(r.text)
        break
    print("❌ リトライ上限到達スキップ", release_id)
    return 0

# --- メール送信 ---
def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.send_message(msg)
        print("✅ 通知メール送信完了")
    except Exception as e:
        print("❌ メール送信失敗:", e)

# --- Discord送信 ---
def send_discord(content):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={'content': content})
        if r.status_code == 204:
            print("✅ Discord送信完了")
        else:
            print("❌ Discord送信失敗:", r.status_code)
    except Exception as e:
        print("❌ Discordエラー:", e)

# --- メイン処理 ---
def main():
    notified = load_notified_counts()
    first_run = len(notified) == 0  # 初回実行判定
    items = get_wantlist_items()
    print(f"取得したWantlist件数: {len(items)}")

    messages = []
    now = datetime.now(JST).strftime('%Y-%m-%d %H:%M')

    for item in items:
        rid = str(item['release_id'])
        count = get_num_for_sale(rid)
        time.sleep(1)
        prev = notified.get(rid)
        # 初回実行時は記録のみ行い、通知はスキップ
        if not first_run and prev is not None and count > prev:
            messages.append(f"💿 {item['title']} - {item['artist']}\n{item['uri']}\n出品数: {count} (前回: {prev})\n")
        # 記録を更新
        notified[rid] = count

    # 通知送信
    if messages:
        header = f"📦 {now} 新規出品通知（{len(messages)}件）\n"
        body = header + '\n'.join(messages)
        send_email("【DISCOGS】Wantlist出品追加まとめ", body)
        send_discord(body)

    save_notified_counts(notified)

if __name__ == '__main__':
    main()
