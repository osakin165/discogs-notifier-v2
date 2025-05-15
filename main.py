import os
import time
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from email.mime.text import MIMEText
import smtplib
from datetime import datetime
import pytz

# —————— Firebase 初期化 ——————
cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

def load_notified_counts():
    doc = db.collection("discogs").document("notified_counts").get()
    if doc.exists:
        return doc.to_dict()
    return {}

def save_notified_counts(data):
    db.collection("discogs").document("notified_counts").set(data)

# —————— 設定読み込み ——————
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
USER_NAME      = os.getenv("USER_NAME")
EMAIL_FROM     = os.getenv("EMAIL_FROM")
EMAIL_TO       = os.getenv("EMAIL_TO")
EMAIL_PASS     = os.getenv("EMAIL_PASS")
DISCORD_WEBHOOK= os.getenv("DISCORD_WEBHOOK_URL")

JST = pytz.timezone("Asia/Tokyo")

# —————— wantlist取得 ——————
def get_wantlist_ids():
    ids, page = [], 1
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    while True:
        url = f'https://api.discogs.com/users/{USER_NAME}/wants?page={page}&per_page=100'
        res = requests.get(url, headers=headers)
        if res.status_code != 200: break
        wants = res.json().get('wants', [])
        if not wants: break
        ids += [item['basic_information']['id'] for item in wants]
        if len(wants)<100: break
        page += 1
    return ids

# —————— num_for_sale取得（リトライ付き） ——————
def get_num_for_sale(release_id, retries=3):
    url = f'https://api.discogs.com/releases/{release_id}'
    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    for attempt in range(retries):
        try:
            res = requests.get(url, headers=headers)
            print(f"🔍 Checking release_id: {release_id}")
            print(f"📦 API Response: {res.status_code}")
            if res.status_code == 200:
                return res.json().get("num_for_sale", 0)
            if res.status_code == 429:
                print("⚠️ 429 → 5秒待って再試行")
                time.sleep(5)
                continue
            # 404などその他
            print(res.text)
            return 0
        except Exception as e:
            print(f"⚠️ 接続エラー: {e}")
            time.sleep(5)
    print(f"❌ リトライ上限到達スキップ {release_id}")
    return 0

# —————— 通知送信 ——————
def send_notifications(messages):
    if not messages:
        print("📝 通知対象なし")
        return

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    subject = f"{now} 新規出品通知（{len(messages)}件）"
    body = subject + "\n\n" + "\n\n".join(messages)

    # --- メール送信 ---
    try:
        msg = MIMEText(body)
        msg['Subject']= subject
        msg['From']   = EMAIL_FROM
        msg['To']     = EMAIL_TO
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_FROM, EMAIL_PASS)
            smtp.send_message(msg)
        print("✅ 通知メールを送信しました。")
    except Exception as e:
        print(f"❌ メール送信に失敗しました: {e}")

    # --- Discord通知 ---
    try:
        payload = {"content": body}
        res = requests.post(DISCORD_WEBHOOK, json=payload)
        if res.status_code == 204:
            print("✅ Discord通知を送信しました。")
        else:
            print(f"❌ Discord通知に失敗: {res.status_code}")
    except Exception as e:
        print(f"❌ Discord送信エラー: {e}")

def main():
    want_ids = get_wantlist_ids()
    print(f"取得したWantlist件数: {len(want_ids)}")

    # Firestoreから履歴読み込み
    notified = load_notified_counts()
    is_first_run = (notified == {})

    # 初回実行時は通知せず、履歴だけ作って終了
    if is_first_run:
        print("初回実行のため通知をスキップし、履歴を初期化します。")
        for rid in want_ids:
            notified[rid] = get_num_for_sale(rid)
            time.sleep(1)
        save_notified_counts(notified)
        return

    # 差分検出ループ
    new_messages = []
    for rid in want_ids:
        current = get_num_for_sale(rid)
        prev = notified.get(rid)
        # 履歴にない商品はスキップ（新Wantlist追加時の初回のみ記録）
        if prev is None:
            print(f"ℹ️ New item detected, skip notifications this run: {rid}")
            notified[rid] = current
            time.sleep(1)
            continue

        # 増加時だけ通知
        if current > prev:
            url = f"https://www.discogs.com/release/{rid}"
            msg = f"💿 {url.split('/')[-1].replace('-', ' ')}\n{url}\n出品数: {current} (前回: {prev})"
            new_messages.append(msg)
        # 減少 or 同数も履歴は更新
        notified[rid] = current
        time.sleep(1)

    # Firestoreに履歴更新
    save_notified_counts(notified)
    # まとめて通知
    send_notifications(new_messages)

if __name__ == "__main__":
    main()
