import requests
from config import BOT_TOKEN, CHAT_ID


def telegram_gonder(mesaj):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": mesaj
            },
            timeout=15
        )

        if r.status_code == 200:
            print("Telegram mesajı gönderildi.")
        else:
            print("Telegram Hatası:", r.text)

    except Exception as e:
        print("Telegram Bağlantı Hatası:", e)
