from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo
import requests
from config import API_URL, SEARCH_POINTS, MAKINE_KURALLARI, OTOMATIK_ERKEN_UYARI_BOLGELERI, TAKIP_KUTULARI
from history_manager import gecmis_kaydi_ekle
from status_manager import durumlari_yukle, durumlari_kaydet
from telegram import telegram_duzenle, telegram_gonder

TZ = ZoneInfo("Europe/Istanbul")
SAMPLE_COUNT = 5
CONFIRM_COUNT = 3


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
    if level <= 20: return "empty"
    if level <= 40: return "available"
    if level <= 79: return "filling"
    if level <= 89: return "nearly_full"
    return "critical"


def band_text(value):
    return {
        "empty": "✅ BOŞALTILMIŞ / ÇOK UYGUN",
        "available": "✅ UYGUN",
        "filling": "🟡 DOLUYOR",
        "nearly_full": "🟠 DOLMAK ÜZERE",
        "critical": "🚨 KRİTİK / DOLUM SINIRINDA",
    }.get(value, "BİLİNMİYOR")


def bar(level):
    count = max(0, min(10, int(round(level / 10))))
    square = "🟩" if level <= 40 else "🟨" if level <= 79 else "🟧" if level <= 89 else "🟥"
    return square * count + "⬜" * (10 - count)


def bin_name(value):
    return {"pet": "PET", "glass": "CAM", "aluminum": "ALÜMİNYUM", "can": "ALÜMİNYUM"}.get(value, value.upper())


def filtered_bin(raw, old=None):
    old = old or {}
    raw_level = clamp(raw.get("level", 0))
    samples = list(old.get("samples", []))[-4:] + [raw_level]
    filtered = int(round(median(samples)))
    measured_band = band(filtered)
    confirmed = old.get("confirmedBand")
    candidate = old.get("candidateBand")
    candidate_count = int(old.get("candidateCount", 0) or 0)
    changed = False
    if confirmed is None:
        confirmed = measured_band
        candidate, candidate_count = None, 0
    elif measured_band == confirmed:
        candidate, candidate_count = None, 0
    else:
        candidate_count = candidate_count + 1 if candidate == measured_band else 1
        candidate = measured_band
        if candidate_count >= CONFIRM_COUNT:
            confirmed, candidate, candidate_count, changed = measured_band, None, 0, True
    return {
        "level": raw_level,
        "state": bool(raw.get("state", False)),
        "samples": samples,
        "filteredLevel": filtered,
        "confirmedBand": confirmed,
        "candidateBand": candidate,
        "candidateCount": candidate_count,
        "_changed": changed,
        "_previousBand": old.get("confirmedBand"),
        "_previousLevel": old.get("filteredLevel", old.get("level")),
    }


def build_state(machine, rule, old=None):
    old = old or {}
    state = {
        "name": machine.get("definition", {}).get("name", "Bilinmeyen Makine"),
        "label": rule["label"], "type": rule["type"],
        "address": machine.get("address"), "latitude": machine.get("latitude"), "longitude": machine.get("longitude"),
        "machineStatus": machine.get("machineStatus"), "active": machine.get("active"), "status": machine.get("status"),
        "openingClosingHours": machine.get("openingClosingHours"),
        "lastChecked": datetime.now(TZ).isoformat(),
        "telegramMessageId": old.get("telegramMessageId"), "bins": {},
    }
    old_bins = old.get("bins", {})
    for item in machine.get("binList", []):
        kind = str(item.get("contentType", "unknown")).strip().lower()
        if kind in TAKIP_KUTULARI:
            state["bins"][kind] = filtered_bin(item, old_bins.get(kind))
    return state


def heading(state):
    return f"🎯 MUĞLA MERKEZ HEDEFİ · {state['label']}" if state["type"] == "target" else f"🚨 ERKEN UYARI · {state['label'].upper()}"


def card(state):
    lines = ["♻️ DOA MAKİNE DURUMU", heading(state), f"📍 {state['name']}", ""]
    for kind, item in state["bins"].items():
        level = item["filteredLevel"]
        lines += [f"{bin_name(kind)} · %{level}", bar(level), band_text(item["confirmedBand"]), ""]
    lines += [f"🕒 Son kontrol: {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}", "ℹ️ Son 5 ölçümün medyanı; değişiklik 3 kontrolde doğrulanır."]
    return "\n".join(lines).strip()


def alert(state):
    lines = []
    for kind, item in state["bins"].items():
        if not item.get("_changed") or item["confirmedBand"] not in {"empty", "nearly_full", "critical"}:
            continue
        title = "✅ BOŞALTILDIĞI DOĞRULANDI" if item["confirmedBand"] == "empty" else "🚨 KRİTİK SEVİYEYE ULAŞTI" if item["confirmedBand"] == "critical" else "🟠 DOLMAK ÜZERE"
        lines += [f"{bin_name(kind)}: {title}", f"{band_text(item['_previousBand'])} → {band_text(item['confirmedBand'])}", f"%{item['_previousLevel']} → %{item['filteredLevel']}", ""]
    if not lines:
        return None
    return "\n".join(["🔔 DOA DOĞRULANMIŞ DEĞİŞİKLİK", heading(state), f"📍 {state['name']}", "", *lines, "Anlık kalibrasyon sıçramaları filtrelendi.", f"🕒 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}"]).strip()


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
    old_states, new_states = durumlari_yukle(), {}
    for machine_id, info in fetch_machines().items():
        machine = info["data"]
        name = machine.get("definition", {}).get("name", "Bilinmeyen Makine")
        rule = classify(name, info["regions"])
        if not rule:
            continue
        state = build_state(machine, rule, old_states.get(machine_id))
        message_id = state.get("telegramMessageId")
        if not message_id or not telegram_duzenle(message_id, card(state)):
            new_id = telegram_gonder(card(state))
            if new_id:
                state["telegramMessageId"] = new_id
        warning = alert(state)
        if warning:
            telegram_gonder(warning)
        gecmis_kaydi_ekle(machine_id, state)
        for item in state["bins"].values():
            item.pop("_changed", None); item.pop("_previousBand", None); item.pop("_previousLevel", None)
        new_states[machine_id] = state
        print(f"Durum kartı güncellendi: {rule['label']} / {name}")
    if not new_states:
        print("Takip edilecek makine bulunamadı.")
        return
    old_states.update(new_states)
    durumlari_kaydet(old_states)
    print(f"Takip edilen makine sayısı: {len(new_states)}")
