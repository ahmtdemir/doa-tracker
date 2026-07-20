import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Europe/Istanbul")
ALARM_HISTORY_FILE = Path("alarm_history.jsonl")


def _bin_record(item):
    return {
        "rawLevel": item.get("level"),
        "displayLevel": item.get("filteredLevel", item.get("level")),
        "displayPrevious": item.get("_previousLevel"),
        "triggerReference": item.get("lastAlertLevel"),
        "rawState": item.get("rawState"),
        "confirmedState": item.get("confirmedState"),
        "previousState": item.get("_previousState"),
        "changed": bool(item.get("_changed", False)),
        "definiteEmptying": bool(item.get("_definiteEmptying", False)),
        "confirmedBand": item.get("confirmedBand"),
        "previousBand": item.get("_previousBand"),
        "stateCandidate": item.get("stateCandidate"),
        "stateCandidateCount": item.get("stateCandidateCount"),
    }


def alarm_kaydi_ekle(machine_id, state, message):
    """Gönderilmek üzere üretilen alarmı pasif olarak JSONL dosyasına yazar.

    Bu fonksiyon hiçbir zaman çağıran alarm akışına hata taşımaz.
    """
    try:
        record = {
            "recordedAt": datetime.now(TZ).isoformat(),
            "machineId": machine_id,
            "name": state.get("name"),
            "label": state.get("label"),
            "type": state.get("type"),
            "operationPriority": state.get("operationPriority"),
            "priorityScore": state.get("priorityScore"),
            "lastChecked": state.get("lastChecked"),
            "simultaneousEmptying": bool(state.get("simultaneousEmptying", False)),
            "bins": {
                kind: _bin_record(item)
                for kind, item in (state.get("bins") or {}).items()
            },
            "message": message,
        }
        with ALARM_HISTORY_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")
    except Exception as error:
        print(f"alarm_history.jsonl yazılamadı; alarm akışı devam ediyor: {error}")
