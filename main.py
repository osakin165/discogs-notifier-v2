import requests
import smtplib
from email.mime.text import MIMEText
import os

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# この関数を既存の get_wantlist_ids() と置き換えてください
def get_wantlist_ids():
    ids = []
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

        page_ids = [item['basic_information']['id'] for item in wants]
        ids.extend(page_ids)

        if len(wants) < 100:
            break  # 最終ページ
        page += 1

    return ids

def check_marketplace(item_id):
    url = f'https://api.discogs.com/marketplace/search?release_id={item_id}&sort=listed,desc'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    response = requests.get(url, headers=headers)
    return response.json().get('results', [])

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
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print("✅ Discord通知を送信しました。")
        else:
            print(f"❌ Discord通知に失敗しました: {response.status_code}")
    except Exception as e:
        print(f"❌ Discord送信エラー: {e}")
        
def main():

    ids = get_wantlist_ids()
    print(f"取得したWantlistのID一覧: {ids}")

    for item_id in ids:
        print(f"🔍 Checking item_id: {item_id}")
        listings = check_marketplace(item_id)
        if listings:
            title = listings[0]["title"]
            uri = listings[0]["uri"]
            message = f"💿 Wantlistに新しい商品が出品されました！\n{title}\n{uri}"
            send_email("【DISCOGS】Wantlist新着商品あり", message)
            send_discord(message)  # Discordに通知
            break
        else:
            print("📭 出品が見つかりませんでした。")

if __name__ == '__main__':
    main()

