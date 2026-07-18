import os

import requests


BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def telegram_gonder(mesaj):
    if not BOT_TOKEN:
        print("Telegram Hatası: TELEGRAM_TOKEN bulunamadı.")
        return False

    if not CHAT_ID:
        print("Telegram Hatası: TELEGRAM_CHAT_ID bulunamadı.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": mesaj,
            },
            timeout=15,
        )

        if response.status_code == 200:
            print("Telegram mesajı gönderildi.")
            return True

        print(
            f"Telegram Hatası ({response.status_code}):",
            response.text,
        )
        return False

    except requests.RequestException as hata:
        print("Telegram Bağlantı Hatası:", hata)
        return False
