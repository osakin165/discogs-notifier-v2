import time
import requests
import smtplib
from email.mime.text import MIMEText
import os
import json
from datetime import datetime, timezone, timedelta

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

RECORD_FILE = "notified_counts.json"
JST = timezone(timedelta(hours=9))

# 通知履歴の読み込み（初回は空）
def load_notified_counts():
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE, 'r') as f:
            return json.load(f)
    return {}

# 通知履歴の保存
def save_notified_counts(data):
    with open(RECORD_FILE, 'w') as f:
        json.dump(data, f)

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
            uri = info.get('resource_url')
            items.append({'release_id': release_id, 'title': title, 'artist': artists, 'uri': uri})

        if len(wants) < 100:
            break
        page += 1

    return items

def get_num_for_sale(release_id):
    url = f'https://api.discogs.com/releases/{release_id}'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    try:
        response = requests.get(url, headers=headers)
        print(f"🔍 Checking release_id: {release_id}")
        print(f"📦 API Response: {response.status_code}")

        if response.status_code != 200:
            print(response.text)
            return 0

        data = response.json()
        return data.get("num_for_sale", 0)

    except Exception as e:
        print(f"⚠️ エラーが発生しました: {e}")
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

    for item in items:
        release_id = str(item['release_id'])
        title = item['title']
        artist = item['artist']
        uri = item['uri']

        num_for_sale = get_num_for_sale(release_id)
        time.sleep(1)

        prev_count = notified_counts.get(release_id, 0)
        if num_for_sale > prev_count:
            msg = f"💿 {title} - {artist}\n{uri}\n出品数: {num_for_sale} (前回: {prev_count})\n"
            messages.append(msg)

        # 出品数が減った場合でも記録を更新しておく
        notified_counts[release_id] = num_for_sale

    if messages:
        full_message = "\n".join(messages)
        send_email("【DISCOGS】出品追加まとめ通知", full_message)
        send_discord(full_message)

    save_notified_counts(notified_counts)

if __name__ == '__main__':
    main()
