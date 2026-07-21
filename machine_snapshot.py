import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SNAPSHOT_FILE = Path("raw_machine_snapshots.json")
TZ = ZoneInfo("Europe/Istanbul")


def save_machine_snapshot(machines):
    payload = {
        "capturedAt": datetime.now(TZ).isoformat(),
        "machines": machines,
    }
    SNAPSHOT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
