import requests
import smtplib
from email.mime.text import MIMEText
import os

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def get_wantlist_ids():
    url = f'https://api.discogs.com/users/{USER_NAME}/wants'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Wantlist取得に失敗しました")
        return []
    wants = response.json().get('wants', [])
    return [item['basic_information']['id'] for item in wants]

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
            break
        else:
            print("📭 出品が見つかりませんでした。")

if __name__ == '__main__':
    main()
