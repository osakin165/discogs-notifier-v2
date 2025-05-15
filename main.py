import os
import time
import smtplib
import requests
import json
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 初期化
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# メール通知設定
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

JST = timezone(timedelta(hours=9))

def load_notified_counts():
    doc = db.collection("discogs").document("notified_counts").get()
    if doc.exists:
        return doc.to_dict()
    return {}

def save_notified_counts(data):
    db.collection("discogs").document("notified_counts").set(data)

def get_wantlist_items():
    items = []
    page = 1
    while True:
        url = f'https://api.discogs.com/users/{USER_NAME}/wants?page={page}&per_page=100'
        headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("❌ Wantlist取得に失敗しました")
            break
        wants = response.json().get('wants', [])
        if not wants:
            break
        for item in wants:
            info = item['basic_information']
            release_id = info.get('id')
            title = info.get('title')
            artists = ', '.join([a['name'] for a in info.get('artists', [])])
            uri = f"https://www.discogs.com/release/{release_id}"  # Web用リンクに変更
            items.append({'release_id': release_id, 'title': title, 'artist': artists, 'uri': uri})
        if len(wants) < 100:
            break
        page += 1
    return items

def get_num_for_sale(release_id, retries=3):
    url = f'https://api.discogs.com/releases/{release_id}'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            print(f"🔍 Checking release_id: {release_id}")
            print(f"📦 API Response: {response.status_code}")
            if response.status_code == 200:
                return response.json().get("num_for_sale", 0)
            elif response.status_code == 429:
                print("⚠️ 429エラー：5秒待って再試行します...")
                time.sleep(5)
            else:
                print(response.text)
                return 0
        except Exception as e:
            print(f"⚠️ エラーが発生しました: {e}")
            return 0
    print("❌ リトライ上限を超えたためスキップします。")
    return 0

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.send_message(msg)
        print("✅ 通知メールを送信しました。")
    except Exception as e:
        print(f"❌ メール送信に失敗しました: {e}")

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("✅ Discord通知を送信しました。")
        else:
            print(f"❌ Discord通知に失敗しました: {response.status_code}")
    except Exception as e:
        print(f"❌ Discord送信エラー: {e}")

def main():
    notified_counts = load_notified_counts()
    items = get_wantlist_items()
    print(f"取得したWantlist件数: {len(items)}")

    messages = []
    now = datetime.now(JST).strftime('%Y-%m-%d %H:%M')

    for item in items:
        release_id = str(item['release_id'])
        title = item['title']
        artist = item['artist']
        uri = item['uri']

        num_for_sale = get_num_for_sale(release_id)
        time.sleep(1)

        # Firestoreに記録がない場合は初回として記録だけして通知は出さない
        if release_id not in notified_counts:
            print(f"📝 初回記録: {release_id} → {num_for_sale}件")
            notified_counts[release_id] = num_for_sale
            continue

        prev_count = notified_counts.get(release_id, 0)
        if num_for_sale > prev_count:
            msg = f"💿 {title} - {artist}\n{uri}\n出品数: {num_for_sale} (前回: {prev_count})\n"
            messages.append(msg)

        notified_counts[release_id] = num_for_sale

    if messages:
        header = f"📦 {now} 新規出品通知（{len(messages)}件）\n"
        full_message = header + "\n".join(messages)
        send_email("【DISCOGS】Wantlist出品追加まとめ", full_message)
        send_discord(full_message)

    save_notified_counts(notified_counts)

if __name__ == '__main__':
    main()
