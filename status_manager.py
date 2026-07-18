import json
from pathlib import Path


STATUS_DOSYASI = Path("status.json")


def durumlari_yukle():
    if not STATUS_DOSYASI.exists():
        return {}

    try:
        with STATUS_DOSYASI.open("r", encoding="utf-8") as dosya:
            veri = json.load(dosya)

        return veri if isinstance(veri, dict) else {}

    except (json.JSONDecodeError, OSError):
        print("status.json okunamadı. Boş durum kullanılacak.")
        return {}


def durumlari_kaydet(durumlar):
    with STATUS_DOSYASI.open("w", encoding="utf-8") as dosya:
        json.dump(
            durumlar,
            dosya,
            ensure_ascii=False,
            indent=2,
            sort_keys=True
        )
