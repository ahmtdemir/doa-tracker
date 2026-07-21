from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

import requests

from alert_formatter import alert, card
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
RATE_HISTORY_COUNT = 96
CONFIRM_COUNT = 3
CARD_VERSION = 4


def norm(value):
    return str(value or "").strip().upper()


def classify(name, regions):
    normalized = norm(name)
    for key, rule in MAKINE_KURALLARI.items():
        if norm(key) in normalized:
            return {"label": rule["label"], "type": rule["type"]}
    for region in regions:
        if region in OTOMATIK_ERKEN_UYARI_BOLGELERI:
            label = next((p["label"] for p in SEARCH_POINTS if p["name"] == region), region)
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


def now():
    return datetime.now(TZ)


def is_night(moment=None):
    hour = (moment or now()).hour
    return hour >= 22 or hour < 8


def learned_tolerance(old, raw_level):
    previous_raw = old.get("level")
    noise_samples = list(old.get("noiseSamples", []))[-(NOISE_HISTORY_COUNT - 1):]
    if previous_raw is not None:
        delta = abs(raw_level - clamp(previous_raw))
        if delta <= 14:
            noise_samples.append(delta)
    base = 8 if is_night() else 5
    learned = int(round(median(noise_samples))) + 2 if noise_samples else base
    return max(base, min(12, learned)), noise_samples


def confirm_boolean(raw_value, old):
    raw_value = bool(raw_value)
    confirmed = old.get("confirmedState")
    candidate = old.get("stateCandidate")
    count = int(old.get("stateCandidateCount", 0) or 0)
    changed = False
    if confirmed is None:
        confirmed = raw_value
        candidate = None
        count = 0
    elif raw_value == confirmed:
        candidate = None
        count = 0
    else:
        count = count + 1 if candidate == raw_value else 1
        candidate = raw_value
        if count >= CONFIRM_COUNT:
            confirmed = raw_value
            candidate = None
            count = 0
            changed = True
    return confirmed, candidate, count, changed


def update_fill_rate(old, filtered, checked_at):
    samples = list(old.get("rateSamples", []))[-(RATE_HISTORY_COUNT - 1):]
    previous_level = old.get("filteredLevel")
    previous_checked = old.get("lastRateChecked")
    if previous_level is not None and previous_checked:
        try:
            previous_dt = datetime.fromisoformat(previous_checked).astimezone(TZ)
            elapsed_hours = (checked_at - previous_dt).total_seconds() / 3600
        except (TypeError, ValueError):
            elapsed_hours = 0
        delta = filtered - clamp(previous_level)
        if 0.05 <= elapsed_hours <= 3 and 0 < delta <= 25 and not is_night(checked_at):
            hourly = delta / elapsed_hours
            if hourly <= 40:
                samples.append(round(hourly, 2))
    avg_rate = round(median(samples), 2) if len(samples) >= 3 else None
    eta_hours = round((100 - filtered) / avg_rate, 1) if avg_rate and avg_rate > 0 and filtered < 100 else None
    return samples, avg_rate, eta_hours


def filtered_bin(raw, old=None, checked_at=None):
    old = old or {}
    checked_at = checked_at or now()
    raw_level = clamp(raw.get("level", 0))
    samples = list(old.get("samples", []))[-(SAMPLE_COUNT - 1):] + [raw_level]
    measured_level = int(round(median(samples)))
    tolerance, noise_samples = learned_tolerance(old, raw_level)
    previous_display = old.get("filteredLevel")
    filtered = measured_level if previous_display is None or abs(measured_level - clamp(previous_display)) > tolerance else clamp(previous_display)

    measured_band = band(filtered)
    confirmed_band = old.get("confirmedBand")
    candidate_band = old.get("candidateBand")
    candidate_count = int(old.get("candidateCount", 0) or 0)
    band_changed = False
    if confirmed_band is None:
        confirmed_band = measured_band
        candidate_band = None
        candidate_count = 0
    elif measured_band == confirmed_band:
        candidate_band = None
        candidate_count = 0
    else:
        candidate_count = candidate_count + 1 if candidate_band == measured_band else 1
        candidate_band = measured_band
        if candidate_count >= CONFIRM_COUNT:
            confirmed_band = measured_band
            candidate_band = None
            candidate_count = 0
            band_changed = True

    confirmed_state, state_candidate, state_count, state_changed = confirm_boolean(raw.get("state", False), old)
    rate_samples, avg_rate, eta_hours = update_fill_rate(old, filtered, checked_at)
    return {
        "level": raw_level,
        "rawState": bool(raw.get("state", False)),
        "confirmedState": confirmed_state,
        "stateCandidate": state_candidate,
        "stateCandidateCount": state_count,
        "samples": samples,
        "noiseSamples": noise_samples,
        "displayTolerance": tolerance,
        "filteredLevel": filtered,
        "confirmedBand": confirmed_band,
        "candidateBand": candidate_band,
        "candidateCount": candidate_count,
        "rateSamples": rate_samples,
        "averageHourlyFill": avg_rate,
        "estimatedHoursToFull": eta_hours,
        "lastRateChecked": checked_at.isoformat(),
        "_changed": band_changed or state_changed,
        "_previousBand": old.get("confirmedBand"),
        "_previousLevel": old.get("filteredLevel", old.get("level")),
        "_previousState": old.get("confirmedState"),
    }


def apply_simultaneous_emptying(state, old):
    old_bins = (old or {}).get("bins", {})
    emptied = []
    for kind, item in state["bins"].items():
        previous = old_bins.get(kind, {})
        previous_level = clamp(previous.get("filteredLevel", previous.get("level", 0)))
        if previous_level >= 80 and item["level"] <= 20 and previous_level - item["level"] >= 60:
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
        item["confirmedState"] = True
        item["stateCandidate"] = None
        item["stateCandidateCount"] = 0
        item["estimatedHoursToFull"] = None
        item["_changed"] = True
        item["_previousBand"] = previous.get("confirmedBand")
        item["_previousLevel"] = previous.get("filteredLevel", previous.get("level"))
    state["simultaneousEmptying"] = True
    state["lastEmptiedAt"] = now().isoformat()
    return True


def machine_priority(state):
    levels = [item["filteredLevel"] for item in state["bins"].values()]
    unsuitable = sum(not item.get("confirmedState", True) for item in state["bins"].values())
    score = (max(levels) if levels else 0) + unsuitable * 15 + (25 if state.get("type") == "target" else 0)
    state["priorityScore"] = score
    state["operationPriority"] = "YÜKSEK" if score >= 115 else "ORTA" if score >= 85 else "DÜŞÜK"


def build_state(machine, rule, old=None):
    old = old or {}
    checked_at = now()
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
        "lastChecked": checked_at.isoformat(),
        "lastEmptiedAt": old.get("lastEmptiedAt"),
        "telegramMessageId": old.get("telegramMessageId"),
        "cardVersion": CARD_VERSION,
        "bins": {},
    }
    old_bins = old.get("bins", {})
    for item in machine.get("binList", []):
        kind = str(item.get("contentType", "unknown")).strip().lower()
        if kind in TAKIP_KUTULARI:
            state["bins"][kind] = filtered_bin(item, old_bins.get(kind), checked_at)
    apply_simultaneous_emptying(state, old)
    machine_priority(state)
    return state


def fetch_machines():
    result = {}
    for point in SEARCH_POINTS:
        payload = {key: point[key] for key in ("lat", "lon", "distance", "userLat", "userLon")}
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
                result.setdefault(machine_id, {"data": machine, "regions": set()})["regions"].add(point["name"])
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
            for key in ("_changed", "_previousBand", "_previousLevel", "_previousState"):
                item.pop(key, None)
        state.pop("simultaneousEmptying", None)
        new_states[machine_id] = state
        print(f"Durum kartı güncellendi: {rule['label']} / {name}")
    if not new_states:
        print("Takip edilecek makine bulunamadı.")
        return
    old_states.update(new_states)
    durumlari_kaydet(old_states)
    print(f"Takip edilen makine sayısı: {len(new_states)}")
