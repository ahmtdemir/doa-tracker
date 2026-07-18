import requests
from config import API_URL, SEARCH_POINTS, TAKIP_MAKINELERI
from telegram import telegram_gonder


def siteyi_test_et():

    tum_makineler = {}

for nokta in SEARCH_POINTS:

    response = requests.post(
        API_URL,
        json=nokta,
        timeout=20
    )

    if response.status_code != 200:
        continue

    data = response.json()

    for makina in data["rvmList"]:

        tum_makineler[makina["id"]] = makina

    if response.status_code != 200:
        print("API Hatası:", response.status_code)
        return

    data = response.json()

    bulundu = False

   for makina in tum_makineler.values():

        isim = makina["definition"]["name"]

        if not any(takip in isim for takip in TAKIP_MAKINELERI):
            continue

        bulundu = True

        mesaj = f"📍 {isim}\n\n"

        for kutu in makina["binList"]:

            durum = "✅ UYGUN" if kutu["state"] else "❌ DOLU"

            mesaj += (
                f"{kutu['contentType'].upper()} : "
                f"{kutu['level']}%  {durum}\n"
            )

        telegram_gonder(mesaj)

    if not bulundu:
        print("Takip edilen makine bulunamadı.")
