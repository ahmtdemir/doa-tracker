import requests

from config import API_URL, SEARCH_POINTS, TAKIP_MAKINELERI
from status_manager import durumlari_yukle, durumlari_kaydet
from telegram import telegram_gonder


def makine_durumu_olustur(makina):
    durum = {
        "name": makina.get("definition", {}).get("name", "Bilinmeyen Makine"),
        "bins": {}
    }

    for kutu in makina.get("binList", []):
        tur = str(kutu.get("contentType", "unknown")).lower()

        durum["bins"][tur] = {
            "level": kutu.get("level", 0),
            "state": bool(kutu.get("state", False))
        }

    return durum


def degisiklik_mesaji_olustur(isim, eski_durum, yeni_durum):
    satirlar = [
        "🔔 DOA Durum Güncellemesi",
        "",
        f"📍 {isim}",
        ""
    ]

    eski_kutular = eski_durum.get("bins", {})
    yeni_kutular = yeni_durum.get("bins", {})

    degisiklik_var = False

    for tur, yeni_kutu in yeni_kutular.items():
        eski_kutu = eski_kutular.get(tur)

        if eski_kutu is None:
            continue

        eski_state = eski_kutu.get("state")
        yeni_state = yeni_kutu.get("state")

        eski_level = eski_kutu.get("level", 0)
        yeni_level = yeni_kutu.get("level", 0)

        if eski_state != yeni_state:
            degisiklik_var = True

            durum_metni = (
                "✅ ARTIK UYGUN"
                if yeni_state
                else "❌ ARTIK DOLU"
            )

            satirlar.append(
                f"{tur.upper()} : {durum_metni}\n"
                f"%{eski_level} → %{yeni_level}"
            )
            satirlar.append("")

    if not degisiklik_var:
        return None

    return "\n".join(satirlar).strip()


def ilk_durum_mesaji_olustur(yeni_durum):
    satirlar = [
        "♻️ DOA Takip Başlatıldı",
        "",
        f"📍 {yeni_durum['name']}",
        ""
    ]

    for tur, kutu in yeni_durum["bins"].items():
        durum_metni = "✅ UYGUN" if kutu["state"] else "❌ DOLU"

        satirlar.append(
            f"{tur.upper()} : %{kutu['level']} {durum_metni}"
        )

    return "\n".join(satirlar)


def siteyi_test_et():
    tum_makineler = {}

    for nokta in SEARCH_POINTS:
        try:
            response = requests.post(
                API_URL,
                json=nokta,
                timeout=20
            )
            response.raise_for_status()

            data = response.json()

        except requests.RequestException as hata:
            print(
                f"API Hatası "
                f"({nokta.get('name', 'Bilinmeyen nokta')}): {hata}"
            )
            continue

        except ValueError:
            print("API geçerli JSON döndürmedi.")
            continue

        for makina in data.get("rvmList", []):
            makina_id = str(makina.get("id", ""))

            if makina_id:
                tum_makineler[makina_id] = makina

    print(f"Toplam bulunan makine: {len(tum_makineler)}")

    eski_durumlar = durumlari_yukle()
    yeni_durumlar = {}

    takip_edilen_bulundu = False

    for makina_id, makina in tum_makineler.items():
        isim = makina.get("definition", {}).get("name", "")

        if not any(
            takip.lower() in isim.lower()
            for takip in TAKIP_MAKINELERI
        ):
            continue

        takip_edilen_bulundu = True

        yeni_durum = makine_durumu_olustur(makina)
        yeni_durumlar[makina_id] = yeni_durum

        eski_durum = eski_durumlar.get(makina_id)

        if eski_durum is None:
            mesaj = ilk_durum_mesaji_olustur(yeni_durum)
            telegram_gonder(mesaj)
            print(f"İlk durum kaydedildi: {isim}")
            continue

        mesaj = degisiklik_mesaji_olustur(
            isim,
            eski_durum,
            yeni_durum
        )

        if mesaj:
            telegram_gonder(mesaj)
            print(f"Durum değişikliği gönderildi: {isim}")
        else:
            print(f"Değişiklik yok: {isim}")

    if not takip_edilen_bulundu:
        print("Takip edilen makine bulunamadı.")
        return

    # Önceki kayıtlardan API'de geçici olarak görünmeyen makineleri korur.
    eski_durumlar.update(yeni_durumlar)
    durumlari_kaydet(eski_durumlar)

    print("status.json güncellendi.")
