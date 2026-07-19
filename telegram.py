import os

import requests

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _hazir_mi():
    if not BOT_TOKEN:
        print("Telegram Hatası: TELEGRAM_TOKEN bulunamadı.")
        return False
    if not CHAT_ID:
        print("Telegram Hatası: TELEGRAM_CHAT_ID bulunamadı.")
        return False
    return True


def telegram_gonder(mesaj):
    """Mesajı gönderir; başarılıysa Telegram message_id döndürür."""
    if not _hazir_mi():
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": mesaj},
            timeout=15,
        )
        if response.status_code == 200:
            veri = response.json()
            mesaj_id = veri.get("result", {}).get("message_id")
            print("Telegram mesajı gönderildi.")
            return mesaj_id
        print(f"Telegram Hatası ({response.status_code}):", response.text)
    except requests.RequestException as hata:
        print("Telegram Bağlantı Hatası:", hata)
    return None


def telegram_duzenle(mesaj_id, mesaj):
    """Daha önce gönderilen durum kartını yerinde günceller."""
    if not _hazir_mi() or not mesaj_id:
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "message_id": int(mesaj_id),
                "text": mesaj,
            },
            timeout=15,
        )
        if response.status_code == 200:
            print("Telegram durum kartı güncellendi.")
            return True
        if response.status_code == 400 and "message is not modified" in response.text:
            return True
        print(f"Telegram düzenleme hatası ({response.status_code}):", response.text)
    except (requests.RequestException, TypeError, ValueError) as hata:
        print("Telegram düzenleme bağlantı hatası:", hata)
    return False
