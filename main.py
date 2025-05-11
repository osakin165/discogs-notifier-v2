import requests
import os
from datetime import datetime, timezone, timedelta

# 環境変数からDiscogsトークンを取得
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
RELEASE_ID = 8297209  # テスト対象のrelease_id

# 日本時間の設定
JST = timezone(timedelta(hours=9))
TODAY_JST = datetime.now(JST).date()
YESTERDAY_JST = TODAY_JST - timedelta(days=1)

def check_release_marketplace(release_id):
    url = f"https://api.discogs.com/marketplace/search?release_id={release_id}&sort=listed,desc"
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}

    try:
        response = requests.get(url, headers=headers)
        print(f"🔍 Checking release_id: {release_id}")
        print(f"📦 API Response: {response.status_code}")

        if response.status_code != 200:
            print("❌ API returned non-200 status.")
            print(response.text)
            return

        data = response.json()
        results = data.get("results", [])

        if not results:
            print("📭 出品が見つかりませんでした。")
            return

        print(f"✅ 出品数: {len(results)} 件")
        for item in results:
            title = item.get("title", "不明")
            uri = item.get("uri", "")
            seller = item.get("seller", {}).get("username", "unknown")
            price = item.get("price", {}).get("value", "?")
            currency = item.get("price", {}).get("currency", "")
            date_listed = item.get("date_listed", "なし")
            print("-------------------------------")
            print(f"💿 タイトル: {title}")
            print(f"🔗 URL: https://www.discogs.com{uri}")
            print(f"👤 出品者: {seller}")
            print(f"💰 価格: {price} {currency}")
            print(f"🕒 出品日: {date_listed}")

    except Exception as e:
        print(f"⚠️ 例外が発生しました: {e}")

if __name__ == '__main__':
    check_release_marketplace(RELEASE_ID)
