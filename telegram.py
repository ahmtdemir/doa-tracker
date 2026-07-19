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


def telegram_gonder(mesaj, chat_id=None):
    """Mesajı gönderir; başarılıysa Telegram message_id döndürür."""
    if not _hazir_mi():
        return None

    hedef_chat = str(chat_id or CHAT_ID)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": hedef_chat, "text": mesaj},
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


def telegram_komutlarini_al(limit=20):
    """Bekleyen metin komutlarını alır ve tekrar işlenmemeleri için onaylar."""
    if not _hazir_mi():
        return []

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(
            url,
            params={"offset": -abs(int(limit)), "limit": limit, "timeout": 0},
            timeout=15,
        )
        response.raise_for_status()
        updates = response.json().get("result", [])
    except (requests.RequestException, ValueError, TypeError) as hata:
        print("Telegram komut okuma hatası:", hata)
        return []

    if updates:
        son_update_id = max(int(item.get("update_id", 0)) for item in updates)
        try:
            requests.get(
                url,
                params={"offset": son_update_id + 1, "limit": 1, "timeout": 0},
                timeout=15,
            )
        except requests.RequestException as hata:
            print("Telegram komut onaylama hatası:", hata)

    komutlar = []
    for update in updates:
        message = update.get("message") or update.get("edited_message") or {}
        text = str(message.get("text") or "").strip()
        chat_id = str((message.get("chat") or {}).get("id") or "")
        if not text or not chat_id:
            continue
        if str(CHAT_ID) != chat_id:
            print(f"Yetkisiz Telegram komutu yok sayıldı: {chat_id}")
            continue
        komutlar.append({"text": text, "chat_id": chat_id})

    return komutlar
