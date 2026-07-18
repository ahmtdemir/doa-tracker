import json
from pathlib import Path


HISTORY_DOSYASI = Path("machine_history.jsonl")


def gecmis_kaydi_ekle(makina_id, durum):
    """
    Bir makinenin o anki durumunu JSON Lines formatında
    machine_history.jsonl dosyasına ekler.

    Her satır bağımsız bir JSON kaydıdır.
    Önceki kayıtların üzerine yazılmaz.
    """

    kayit = {
        "machineId": makina_id,
        **durum,
    }

    try:
        with HISTORY_DOSYASI.open(
            "a",
            encoding="utf-8",
        ) as dosya:
            dosya.write(
                json.dumps(
                    kayit,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            dosya.write("\n")

    except OSError as hata:
        print(
            "machine_history.jsonl yazılamadı: "
            f"{hata}"
        )
