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
    Makine adı config.py içindeki kurallardan biriyle eşleşiyorsa
    kesin bölge ve takip türünü döndürür.
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

    1. config.py içinde adı açıkça tanımlanmış makineler
    2. Ula veya Yatağan arama bölgesinde bulunan makineler
    3. Diğer makineler takip edilmez
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
    """
    API'den gelen makine ve hazne durumlarını status.json
    içine kaydedilecek standart yapıya dönüştürür.

    machineStatus, active ve status alanlarının anlamına
    henüz karar vermiyoruz; yalnızca veri topluyoruz.
    """

    isim = makina.get("definition", {}).get(
        "name",
        "Bilinmeyen Makine",
    )

    durum = {
        "name": isim,
        "label": siniflandirma["label"],
        "type": siniflandirma["type"],

        # Makine kimlik ve konum bilgileri
        "address": makina.get("address"),
        "latitude": makina.get("latitude"),
        "longitude": makina.get("longitude"),

        # Makine seviyesindeki durum alanları
        "machineStatus": makina.get("machineStatus"),
        "active": makina.get("active"),
        "status": makina.get("status"),

        # API'nin gösterdiği çalışma saati bilgisi
        "openingClosingHours": makina.get(
            "openingClosingHours"
        ),

        # Kaydın en son ne zaman güncellendiği
        "lastChecked": datetime.now(
            TURKIYE_SAATI
        ).isoformat(),

        "bins": {},
    }

    for kutu in makina.get("binList", []):
        kutu_turu = str(
            kutu.get("contentType", "unknown")
        ).strip().lower()

        if kutu_turu not in TAKIP_KUTULARI:
            continue

        durum["bins"][kutu_turu] = {
            "level": kutu.get("level", 0),
            "state": bool(
                kutu.get("state", False)
            ),
        }

    return durum


def baslik_olustur(yeni_durum):
    if yeni_durum["type"] == "target":
        return (
            "🎯 MUĞLA MERKEZ HEDEFİ\n"
            f"📌 Bölge: {yeni_durum['label']}"
        )

    return (
        f"🚨 ERKEN UYARI — {yeni_durum['label'].upper()}\n"
        "Muğla merkez için ekip hareketi olabilir."
    )


def kutu_adi_duzenle(kutu_turu):
    isimler = {
        "pet": "PET",
        "glass": "GLASS",
        "aluminum": "ALUMINUM",
        "can": "ALUMINUM",
    }

    return isimler.get(
        kutu_turu,
        kutu_turu.upper(),
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
            f"{kutu_adi_duzenle(kutu_turu)}: "
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

    degisen_kutular = []
    bildirim_gerekli = False

    for kutu_turu, yeni_kutu in yeni_kutular.items():
        eski_kutu = eski_kutular.get(kutu_turu)

        if eski_kutu is None:
            continue

        eski_state = bool(
            eski_kutu.get("state", False)
        )
        yeni_state = bool(
            yeni_kutu.get("state", False)
        )

        # UYGUN / DOLU durumu değişmediyse
        # bildirim sebebi oluşturmaz.
        if eski_state == yeni_state:
            continue

        # Erken uyarı makinelerinde sadece
        # DOLU -> UYGUN değişimi bildirim oluşturur.
        if (
            yeni_durum["type"] == "early_warning"
            and not yeni_state
        ):
            print(
                "Erken uyarı bildirimi atlandı: "
                f"{yeni_durum['label']} / "
                f"{yeni_durum['name']} / "
                f"{kutu_adi_duzenle(kutu_turu)} "
                "artık dolu"
            )
            continue

        bildirim_gerekli = True
        degisen_kutular.append(kutu_turu)

    if not bildirim_gerekli:
        return None

    durum_satirlari = []

    for kutu_turu, yeni_kutu in yeni_kutular.items():
        kutu_adi = kutu_adi_duzenle(
            kutu_turu
        )

        yeni_state = bool(
            yeni_kutu.get("state", False)
        )
        yeni_seviye = yeni_kutu.get(
            "level",
            0,
        )

        eski_kutu = eski_kutular.get(
            kutu_turu,
            {},
        )

        eski_seviye = eski_kutu.get(
            "level",
            0,
        )

        if kutu_turu in degisen_kutular:
            if yeni_state:
                durum_metni = "✅ ARTIK UYGUN"
            else:
                durum_metni = "❌ ARTIK DOLU"

            durum_satirlari.extend([
                f"{kutu_adi}: {durum_metni}",
                f"%{eski_seviye} → %{yeni_seviye}",
                "",
            ])

        else:
            durum_metni = (
                "✅ UYGUN"
                if yeni_state
                else "❌ DOLU"
            )

            durum_satirlari.append(
                f"{kutu_adi}: "
                f"%{yeni_seviye} {durum_metni}"
            )

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
        *durum_satirlari,
        "",
        f"🕒 {saat}",
    ]

    return "\n".join(satirlar).strip()


def makineleri_api_den_al():
    """
    SEARCH_POINTS içindeki bütün arama noktalarını sorgular.

    Aynı makine birden fazla bölgede görünürse makine ID'si
    üzerinden tekilleştirir ve görüldüğü bölgeleri saklar.
    """

    tum_makineler = {}

    for nokta in SEARCH_POINTS:
        bolge_adi = nokta["name"]
        bolge_etiketi = nokta.get(
            "label",
            bolge_adi,
        )

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
                f"API Hatası "
                f"({bolge_etiketi}): {hata}"
            )
            continue

        except ValueError:
            print(
                "Geçersiz JSON cevabı: "
                f"{bolge_etiketi}"
            )
            continue

        makineler = data.get(
            "rvmList",
            [],
        )

        print(
            f"{bolge_etiketi} sorgusu: "
            f"{len(makineler)} makine"
        )

        for makina in makineler:
            makina_id = str(
                makina.get("id", "")
            ).strip()

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
        "Tekilleştirilmiş toplam makine: "
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

        if siniflandirma is None:
            continue

        takip_edilen_sayi += 1

        yeni_durum = makina_durumu_olustur(
            makina,
            siniflandirma,
        )

        yeni_durumlar[makina_id] = yeni_durum

        eski_durum = eski_durumlar.get(
            makina_id
        )

        if eski_durum is None:
            mesaj = ilk_durum_mesaji_olustur(
                yeni_durum
            )

            telegram_gonder(mesaj)

            print(
                "İlk durum kaydedildi: "
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
                "Durum değişikliği gönderildi: "
                f"{siniflandirma['label']} / "
                f"{makina_ismi}"
            )
        else:
            print(
                "Bildirim gerektiren değişiklik yok: "
                f"{siniflandirma['label']} / "
                f"{makina_ismi}"
            )

    if takip_edilen_sayi == 0:
        print(
            "Takip edilecek makine bulunamadı."
        )
        return

    # API'de geçici olarak görünmeyen eski makineleri
    # silmeden korur.
    eski_durumlar.update(
        yeni_durumlar
    )

    durumlari_kaydet(
        eski_durumlar
    )

    print(
        "Takip edilen makine sayısı: "
        f"{takip_edilen_sayi}"
    )
    print("status.json güncellendi.")
