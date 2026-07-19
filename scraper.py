from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

import requests

from config import (
    API_URL,
    SEARCH_POINTS,
    MAKINE_KURALLARI,
    OTOMATIK_ERKEN_UYARI_BOLGELERI,
    TAKIP_KUTULARI,
)
from history_manager import gecmis_kaydi_ekle
from status_manager import durumlari_yukle, durumlari_kaydet
from telegram import telegram_duzenle, telegram_gonder

TZ = ZoneInfo("Europe/Istanbul")
SAMPLE_COUNT = 5
NOISE_HISTORY_COUNT = 48
CONFIRM_COUNT = 3
CARD_VERSION = 3


def norm(value):
    return str(value or "").strip().upper()


def classify(name, regions):
    normalized = norm(name)
    for key, rule in MAKINE_KURALLARI.items():
        if norm(key) in normalized:
            return {"label": rule["label"], "type": rule["type"]}

    for region in regions:
        if region in OTOMATIK_ERKEN_UYARI_BOLGELERI:
            label = next(
                (point["label"] for point in SEARCH_POINTS if point["name"] == region),
                region,
            )
            return {"label": label, "type": "early_warning"}

    return None


def clamp(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def band(level):
    if level <= 20:
        return "empty"
    if level <= 40:
        return "available"
    if level <= 79:
        return "filling"
    if level <= 89:
        return "nearly_full"
    return "critical"


def bar(level):
    count = max(0, min(10, int(round(level / 10))))
    if level <= 40:
        square = "🟩"
    elif level <= 79:
        square = "🟨"
    elif level <= 89:
        square = "🟧"
    else:
        square = "🟥"
    return square * count + "⬜" * (10 - count)


def bin_name(value):
    return {
        "pet": "PET",
        "glass": "CAM",
        "aluminum": "ALÜMİNYUM",
        "can": "ALÜMİNYUM",
    }.get(value, value.upper())


def is_night():
    hour = datetime.now(TZ).hour
    return hour >= 22 or hour < 8


def learned_tolerance(old, raw_level):
    """Makinenin küçük sensör oynamalarından kendine uygun tolerans öğrenir."""
    previous_raw = old.get("level")
    noise_samples = list(old.get("noiseSamples", []))[-(NOISE_HISTORY_COUNT - 1):]

    if previous_raw is not None:
        delta = abs(raw_level - clamp(previous_raw))
        if delta <= 14:
            noise_samples.append(delta)

    base = 8 if is_night() else 5
    learned = int(round(median(noise_samples))) + 2 if noise_samples else base
    tolerance = max(base, min(12, learned))
    return tolerance, noise_samples


def filtered_bin(raw, old=None):
    old = old or {}
    raw_level = clamp(raw.get("level", 0))
    samples = list(old.get("samples", []))[-(SAMPLE_COUNT - 1):] + [raw_level]
    measured_level = int(round(median(samples)))

    tolerance, noise_samples = learned_tolerance(old, raw_level)
    previous_display = old.get("filteredLevel")
    if previous_display is None:
        filtered = measured_level
    elif abs(measured_level - clamp(previous_display)) <= tolerance:
        filtered = clamp(previous_display)
    else:
        filtered = measured_level

    measured_band = band(filtered)
    confirmed = old.get("confirmedBand")
    candidate = old.get("candidateBand")
    candidate_count = int(old.get("candidateCount", 0) or 0)
    changed = False

    if confirmed is None:
        confirmed = measured_band
        candidate = None
        candidate_count = 0
    elif measured_band == confirmed:
        candidate = None
        candidate_count = 0
    else:
        candidate_count = candidate_count + 1 if candidate == measured_band else 1
        candidate = measured_band
        if candidate_count >= CONFIRM_COUNT:
            confirmed = measured_band
            candidate = None
            candidate_count = 0
            changed = True

    return {
        "level": raw_level,
        "state": bool(raw.get("state", False)),
        "samples": samples,
        "noiseSamples": noise_samples,
        "displayTolerance": tolerance,
        "filteredLevel": filtered,
        "confirmedBand": confirmed,
        "candidateBand": candidate,
        "candidateCount": candidate_count,
        "_changed": changed,
        "_previousBand": old.get("confirmedBand"),
        "_previousLevel": old.get("filteredLevel", old.get("level")),
    }


def apply_simultaneous_emptying(state, old):
    """İki veya daha fazla hazne aynı anda sert düşerse boşaltmayı anında doğrular."""
    old_bins = (old or {}).get("bins", {})
    emptied = []

    for kind, item in state["bins"].items():
        previous = old_bins.get(kind, {})
        previous_level = clamp(previous.get("filteredLevel", previous.get("level", 0)))
        raw_level = item["level"]

        if previous_level >= 80 and raw_level <= 20 and previous_level - raw_level >= 60:
            emptied.append(kind)

    if len(emptied) < 2:
        return False

    for kind in emptied:
        item = state["bins"][kind]
        previous = old_bins.get(kind, {})
        item["filteredLevel"] = item["level"]
        item["confirmedBand"] = "empty"
        item["candidateBand"] = None
        item["candidateCount"] = 0
        item["_changed"] = previous.get("confirmedBand") != "empty"
        item["_previousBand"] = previous.get("confirmedBand")
        item["_previousLevel"] = previous.get("filteredLevel", previous.get("level"))

    state["simultaneousEmptying"] = True
    return True


def build_state(machine, rule, old=None):
    old = old or {}
    state = {
        "name": machine.get("definition", {}).get("name", "Bilinmeyen Makine"),
        "label": rule["label"],
        "type": rule["type"],
        "address": machine.get("address"),
        "latitude": machine.get("latitude"),
        "longitude": machine.get("longitude"),
        "machineStatus": machine.get("machineStatus"),
        "active": machine.get("active"),
        "status": machine.get("status"),
        "openingClosingHours": machine.get("openingClosingHours"),
        "lastChecked": datetime.now(TZ).isoformat(),
        "telegramMessageId": old.get("telegramMessageId"),
        "cardVersion": CARD_VERSION,
        "bins": {},
    }

    old_bins = old.get("bins", {})
    for item in machine.get("binList", []):
        kind = str(item.get("contentType", "unknown")).strip().lower()
        if kind in TAKIP_KUTULARI:
            state["bins"][kind] = filtered_bin(item, old_bins.get(kind))

    apply_simultaneous_emptying(state, old)
    return state


def heading(state):
    if state["type"] == "target":
        return f"🎯 MUĞLA MERKEZ HEDEFİ · {state['label']}"
    return f"🚨 ERKEN UYARI · {state['label'].upper()}"


def suitability_text(item):
    return "✅ UYGUN" if item.get("state") else "❌ UYGUN DEĞİL"


def card(state):
    lines = [
        "♻️ DOA MAKİNE DURUMU",
        heading(state),
        f"📍 {state['name']}",
        "",
    ]

    for kind, item in state["bins"].items():
        level = item["filteredLevel"]
        lines.extend([
            bin_name(kind),
            bar(level),
            f"%{level} · {suitability_text(item)}",
            "",
        ])

    lines.append(f"🕒 Son kontrol: {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines).strip()


def alert(state):
    lines = []

    for kind, item in state["bins"].items():
        if not item.get("_changed"):
            continue
        if item["confirmedBand"] not in {"empty", "nearly_full", "critical"}:
            continue

        if item["confirmedBand"] == "empty":
            title = "✅ BOŞALTILDI"
        elif item.get("state"):
            title = "🟠 DOLULUK YÜKSELDİ — HÂLÂ UYGUN"
        else:
            title = "❌ UYGUN DEĞİL"

        lines.extend([
            f"{bin_name(kind)}: {title}",
            f"%{item['_previousLevel']} → %{item['filteredLevel']}",
            "",
        ])

    if not lines:
        return None

    event_title = "✅ MAKİNE BOŞALTILDI" if state.get("simultaneousEmptying") else "🔔 DOA DURUM DEĞİŞİKLİĞİ"
    return "\n".join([
        event_title,
        heading(state),
        f"📍 {state['name']}",
        "",
        *lines,
        f"🕒 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}",
    ]).strip()


def fetch_machines():
    result = {}

    for point in SEARCH_POINTS:
        payload = {
            key: point[key]
            for key in ("lat", "lon", "distance", "userLat", "userLon")
        }

        try:
            response = requests.post(API_URL, json=payload, timeout=20)
            response.raise_for_status()
            machines = response.json().get("rvmList", [])
        except (requests.RequestException, ValueError) as error:
            print(f"API Hatası ({point.get('label', point['name'])}): {error}")
            continue

        for machine in machines:
            machine_id = str(machine.get("id", "")).strip()
            if machine_id:
                result.setdefault(
                    machine_id,
                    {"data": machine, "regions": set()},
                )["regions"].add(point["name"])

    return result


def siteyi_test_et():
    old_states = durumlari_yukle()
    new_states = {}

    for machine_id, info in fetch_machines().items():
        machine = info["data"]
        name = machine.get("definition", {}).get("name", "Bilinmeyen Makine")
        rule = classify(name, info["regions"])
        if not rule:
            continue

        old_state = old_states.get(machine_id, {})
        state = build_state(machine, rule, old_state)

        message_id = state.get("telegramMessageId")
        needs_new_card = old_state.get("cardVersion") != CARD_VERSION

        if needs_new_card or not message_id or not telegram_duzenle(message_id, card(state)):
            new_id = telegram_gonder(card(state))
            if new_id:
                state["telegramMessageId"] = new_id

        warning = alert(state)
        if warning:
            telegram_gonder(warning)

        gecmis_kaydi_ekle(machine_id, state)

        for item in state["bins"].values():
            item.pop("_changed", None)
            item.pop("_previousBand", None)
            item.pop("_previousLevel", None)

        state.pop("simultaneousEmptying", None)
        new_states[machine_id] = state
        print(f"Durum kartı güncellendi: {rule['label']} / {name}")

    if not new_states:
        print("Takip edilecek makine bulunamadı.")
        return

    old_states.update(new_states)
    durumlari_kaydet(old_states)
    print(f"Takip edilen makine sayısı: {len(new_states)}")
