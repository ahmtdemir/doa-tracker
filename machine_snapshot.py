import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from config import API_URL, SEARCH_POINTS

SNAPSHOT_FILE = Path("raw_machine_snapshots.json")
TZ = ZoneInfo("Europe/Istanbul")


def collect_machines():
    machines_by_id = {}
    for point in SEARCH_POINTS:
        payload = {key: point[key] for key in ("lat", "lon", "distance", "userLat", "userLon")}
        response = requests.post(API_URL, json=payload, timeout=20)
        response.raise_for_status()
        for machine in response.json().get("rvmList", []):
            machine_id = str(machine.get("id", "")).strip()
            if not machine_id:
                continue
            entry = machines_by_id.setdefault(machine_id, {"regions": [], "data": machine})
            if point["name"] not in entry["regions"]:
                entry["regions"].append(point["name"])
    return machines_by_id


def save_machine_snapshot(machines):
    payload = {
        "capturedAt": datetime.now(TZ).isoformat(),
        "machines": machines,
    }
    SNAPSHOT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    machines = collect_machines()
    save_machine_snapshot(machines)
    print(f"Ham API görüntüsü kaydedildi: {len(machines)} makine")
