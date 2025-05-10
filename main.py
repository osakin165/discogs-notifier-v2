import time
import requests
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime, timezone, timedelta

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# JSTの当日の日付を取得
JST = timezone(timedelta(hours=9))
TODAY_JST = datetime.now(JST).date()

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

def get_today_listings(release_id):
    url = f'https://api.discogs.com/marketplace/search?release_id={release_id}&sort=listed,desc'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    response = requests.get(url, headers=headers)
    print(f"🔍 Checking release_id: {release_id}")
    print(f"📦 API Response: {response.status_code}")

    if response.status_code != 200:
        return []

    listings = response.json().get('results', [])
    today_listed = []
    for item in listings:
        listed_str = item.get('date_listed')  # UTC ISO8601
        try:
            listed_dt = datetime.strptime(listed_str, "%Y-%m-%dT%H:%M:%S%z")
            listed_jst = listed_dt.astimezone(JST)
            if listed_jst.date() == TODAY_JST:
                today_listed.append(item)
        except Exception as e:
            print(f"⚠️ 日付パースエラー: {e}")

    return today_listed

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
    items = get_wantlist_items()
    print(f"取得したWantlist件数: {len(items)}")

    for item in items:
        release_id = item['release_id']
        title = item['title']
        artist = item['artist']
        uri = item['uri']

        today_items = get_today_listings(release_id)
        time.sleep(1)

        for listing in today_items:
            price = listing.get('price', {}).get('value', '?')
            currency = listing.get('price', {}).get('currency', '')
            message = f"💿 本日新着の出品が見つかりました！\n{title} - {artist}\n{listing['uri']}\n価格: {price} {currency}"
            send_email("【DISCOGS】本日新着出品のお知らせ", message)
            send_discord(message)

if __name__ == '__main__':
    main()
