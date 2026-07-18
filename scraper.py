from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from config import (
    API_URL,
    SEARCH_POINTS,
    MAKINE_KURALLARI,
    OTOMATIK_ERKEN_UYARI_BOLGELERI,
    TAKIP_KUTULARI,
)
from status_manager import durumlari_yukle, durumlari_kaydet
from telegram import telegram_gonder


TURKIYE_SAATI = ZoneInfo("Europe/Istanbul")


def metni_normalize_et(metin):
    return str(metin or "").strip().upper()


def makina_kuralini_bul(makina_ismi):
    """
    Makine adı, config.py içindeki isimlerden biriyle eşleşiyorsa
    o makinenin kesin bölge ve tür bilgisini döndürür.
    """

    normalize_isim = metni_normalize_et(makina_ismi)

    for aranan_isim, kural in MAKINE_KURALLARI.items():
        if metni_normalize_et(aranan_isim) in normalize_isim:
            return {
                "label": kural["label"],
                "type": kural["type"],
            }

    return None


def makina_siniflandir(makina_ismi, bulundugu_bolgeler):
    """
    Öncelik sırası:

    1. İsmi config.py içinde açıkça tanımlanmış makineler
    2. Ula veya Yatağan sorgusunda bulunan makineler
    3. Bunların dışındaki makineler takip edilmez
    """

    kesin_kural = makina_kuralini_bul(makina_ismi)

    if kesin_kural:
        return kesin_kural

    for bolge in bulundugu_bolgeler:
        if bolge in OTOMATIK_ERKEN_UYARI_BOLGELERI:
            bolge_etiketi = next(
                (
                    nokta["label"]
                    for nokta in SEARCH_POINTS
                    if nokta["name"] == bolge
                ),
                bolge,
            )

            return {
                "label": bolge_etiketi,
                "type": "early_warning",
            }

    return None


def makina_durumu_olustur(makina, siniflandirma):
    isim = makina.get("definition", {}).get(
        "name",
        "Bilinmeyen Makine",
    )

    durum = {
        "name": isim,
        "label": siniflandirma["label"],
        "type": siniflandirma["type"],
        "bins": {},
    }

    for kutu in makina.get("binList", []):
        kutu_turu = str(
            kutu.get("contentType", "unknown")
        ).lower()

        if kutu_turu not in TAKIP_KUTULARI:
            continue

        durum["bins"][kutu_turu] = {
            "level": kutu.get("level", 0),
            "state": bool(kutu.get("state", False)),
        }

    return durum


def baslik_olustur(yeni_durum):
    if yeni_durum["type"] == "target":
        return (
            f"🎯 MUĞLA MERKEZ HEDEFİ\n"
            f"📌 Bölge: {yeni_durum['label']}"
        )

    return (
        f"🚨 ERKEN UYARI — {yeni_durum['label'].upper()}\n"
        f"Muğla merkez için ekip hareketi olabilir."
    )


def ilk_durum_mesaji_olustur(yeni_durum):
    satirlar = [
        "♻️ DOA Takip Kaydı",
        "",
        baslik_olustur(yeni_durum),
        "",
        f"📍 {yeni_durum['name']}",
        "",
    ]

    for kutu_turu, kutu in yeni_durum["bins"].items():
        durum_metni = (
            "✅ UYGUN"
            if kutu["state"]
            else "❌ DOLU"
        )

        satirlar.append(
            f"{kutu_turu.upper()} : "
            f"%{kutu['level']} {durum_metni}"
        )

    saat = datetime.now(TURKIYE_SAATI).strftime(
        "%d.%m.%Y %H:%M"
    )

    satirlar.extend([
        "",
        f"🕒 {saat}",
    ])

    return "\n".join(satirlar)


def degisiklik_mesaji_olustur(eski_durum, yeni_durum):
    eski_kutular = eski_durum.get("bins", {})
    yeni_kutular = yeni_durum.get("bins", {})

    degisiklik_satirlari = []

    for kutu_turu, yeni_kutu in yeni_kutular.items():
        eski_kutu = eski_kutular.get(kutu_turu)

        if eski_kutu is None:
            continue

        eski_state = bool(eski_kutu.get("state", False))
        yeni_state = bool(yeni_kutu.get("state", False))

        # Yalnızca UYGUN / DOLU durumu değiştiğinde mesaj gönder.
        if eski_state == yeni_state:
            continue

        eski_seviye = eski_kutu.get("level", 0)
        yeni_seviye = yeni_kutu.get("level", 0)

        if yeni_state:
            durum_metni = "✅ ARTIK UYGUN"
        else:
            durum_metni = "❌ ARTIK DOLU"

        degisiklik_satirlari.extend([
            f"{kutu_turu.upper()} : {durum_metni}",
            f"%{eski_seviye} → %{yeni_seviye}",
            "",
        ])

    if not degisiklik_satirlari:
        return None

    saat = datetime.now(TURKIYE_SAATI).strftime(
        "%d.%m.%Y %H:%M"
    )

    satirlar = [
        "🔔 DOA Durum Güncellemesi",
        "",
        baslik_olustur(yeni_durum),
        "",
        f"📍 {yeni_durum['name']}",
        "",
        *degisiklik_satirlari,
        f"🕒 {saat}",
    ]

    return "\n".join(satirlar).strip()


def makineleri_api_den_al():
    """
    Tüm arama noktalarını sorgular.

    Aynı makine birden fazla bölgede görünürse ID üzerinden
    tek kayıtta birleştirir ve görüldüğü bölgeleri saklar.
    """

    tum_makineler = {}

    for nokta in SEARCH_POINTS:
        bolge_adi = nokta["name"]

        payload = {
            "lat": nokta["lat"],
            "lon": nokta["lon"],
            "distance": nokta["distance"],
            "userLat": nokta["userLat"],
            "userLon": nokta["userLon"],
        }

        try:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=20,
            )

            response.raise_for_status()
            data = response.json()

        except requests.RequestException as hata:
            print(
                f"API Hatası ({nokta['label']}): {hata}"
            )
            continue

        except ValueError:
            print(
                f"Geçersiz JSON cevabı: {nokta['label']}"
            )
            continue

        makineler = data.get("rvmList", [])

        print(
            f"{nokta['label']} sorgusu: "
            f"{len(makineler)} makine"
        )

        for makina in makineler:
            makina_id = str(makina.get("id", "")).strip()

            if not makina_id:
                continue

            if makina_id not in tum_makineler:
                tum_makineler[makina_id] = {
                    "data": makina,
                    "regions": set(),
                }

            tum_makineler[makina_id]["regions"].add(
                bolge_adi
            )

    return tum_makineler


def siteyi_test_et():
    tum_makineler = makineleri_api_den_al()

    print(
        f"Tekilleştirilmiş toplam makine: "
        f"{len(tum_makineler)}"
    )

    eski_durumlar = durumlari_yukle()
    yeni_durumlar = {}

    takip_edilen_sayi = 0

    for makina_id, makina_bilgisi in tum_makineler.items():
        makina = makina_bilgisi["data"]
        bulundugu_bolgeler = makina_bilgisi["regions"]

        makina_ismi = makina.get(
            "definition",
            {},
        ).get(
            "name",
            "Bilinmeyen Makine",
        )

        siniflandirma = makina_siniflandir(
            makina_ismi,
            bulundugu_bolgeler,
        )

        # Muğla hedefi, Milas, Ula veya Yatağan değilse izleme.
        if siniflandirma is None:
            continue

        takip_edilen_sayi += 1

        yeni_durum = makina_durumu_olustur(
            makina,
            siniflandirma,
        )

        yeni_durumlar[makina_id] = yeni_durum

        eski_durum = eski_durumlar.get(makina_id)

        if eski_durum is None:
            mesaj = ilk_durum_mesaji_olustur(
                yeni_durum
            )

            telegram_gonder(mesaj)

            print(
                f"İlk durum kaydedildi: "
                f"{siniflandirma['label']} / "
                f"{makina_ismi}"
            )
            continue

        mesaj = degisiklik_mesaji_olustur(
            eski_durum,
            yeni_durum,
        )

        if mesaj:
            telegram_gonder(mesaj)

            print(
                f"Durum değişikliği gönderildi: "
                f"{siniflandirma['label']} / "
                f"{makina_ismi}"
            )
        else:
            print(
                f"Değişiklik yok: "
                f"{siniflandirma['label']} / "
                f"{makina_ismi}"
            )

    if takip_edilen_sayi == 0:
        print("Takip edilecek makine bulunamadı.")
        return

    # API'de geçici olarak görünmeyen eski makinelerin
    # kayıtlarını silmeden korur.
    eski_durumlar.update(yeni_durumlar)

    durumlari_kaydet(eski_durumlar)

    print(
        f"Takip edilen makine sayısı: "
        f"{takip_edilen_sayi}"
    )
    print("status.json güncellendi.")
