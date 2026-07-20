from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote

TZ = ZoneInfo("Europe/Istanbul")
RETURN_CONFIRM_COUNT = 3


def clamp(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def make_bar(level):
    level = clamp(level)
    count = max(0, min(10, int(round(level / 10))))
    symbol = "🟩" if level <= 40 else "🟨" if level <= 79 else "🟧" if level <= 89 else "🟥"
    return symbol * count + "⬜" * (10 - count)


def bin_label(kind):
    return {"pet": "PET", "glass": "CAM", "aluminum": "ALÜMİNYUM", "can": "ALÜMİNYUM"}.get(kind, str(kind).upper())


def suitability_text(item):
    return "✅ UYGUN" if bool(item.get("confirmedState", False)) else "❌ UYGUN DEĞİL"


def map_url(state):
    lat = state.get("latitude")
    lon = state.get("longitude")
    if lat is not None and lon is not None:
        try:
            return f"https://www.google.com/maps/search/?api=1&query={float(lat):.6f},{float(lon):.6f}"
        except (TypeError, ValueError):
            pass
    address = str(state.get("address") or state.get("name") or "").strip()
    return f"https://www.google.com/maps/search/?api=1&query={quote(address)}" if address else None


def map_line(state):
    url = map_url(state)
    return f"🗺️ Haritada aç: {url}" if url else None


def eta_text(item):
    hours = item.get("estimatedHoursToFull")
    if hours is None:
        return None
    if hours < 1:
        return "⏳ Tahmini dolum: 1 saatten az"
    if hours < 24:
        return f"⏳ Tahmini dolum: ≈ {hours:g} saat"
    return f"⏳ Tahmini dolum: ≈ {hours / 24:.1f} gün"


def safe_confirm_boolean(raw_value, old):
    raw_value = bool(raw_value)
    confirmed = old.get("confirmedState")
    candidate = old.get("stateCandidate")
    count = int(old.get("stateCandidateCount", 0) or 0)
    if confirmed is None:
        return raw_value, None, 0, False
    if not raw_value:
        return False, None, 0, confirmed is True
    if confirmed is True:
        return True, None, 0, False
    count = count + 1 if candidate is True else 1
    if count >= RETURN_CONFIRM_COUNT:
        return True, None, 0, True
    return False, True, count, False


def safe_apply_simultaneous_emptying(state, old):
    old_bins = (old or {}).get("bins", {})
    emptied = []
    for kind, item in state.get("bins", {}).items():
        previous = old_bins.get(kind, {})
        previous_level = clamp(previous.get("filteredLevel", previous.get("level", 0)))
        current_level = clamp(item.get("level", 0))
        if previous_level >= 80 and current_level <= 20 and previous_level - current_level >= 60:
            emptied.append(kind)
    if len(emptied) < 2:
        return False
    for kind in emptied:
        item = state["bins"][kind]
        previous = old_bins.get(kind, {})
        item["filteredLevel"] = clamp(item.get("level", 0))
        item["confirmedBand"] = "empty"
        item["candidateBand"] = None
        item["candidateCount"] = 0
        item["estimatedHoursToFull"] = None
        item["_changed"] = True
        item["_previousBand"] = previous.get("confirmedBand")
        item["_previousLevel"] = previous.get("filteredLevel", previous.get("level"))
    state["simultaneousEmptying"] = True
    state["lastEmptiedAt"] = datetime.now(TZ).isoformat()
    return True


def heading(state):
    region = state.get("label", "")
    return f"🎯 MUĞLA MERKEZ HEDEFİ · {region}" if state.get("type") == "target" else f"🚨 ERKEN UYARI · {str(region).upper()}"


def card(state):
    lines = [
        "♻️ DOA MAKİNE DURUMU",
        heading(state),
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"🚚 Operasyon önceliği: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
    ]
    for kind, item in (state.get("bins") or {}).items():
        level = clamp(item.get("filteredLevel", item.get("level", 0)))
        lines.extend([bin_label(kind), make_bar(level), f"%{level} · {suitability_text(item)}"])
        estimate = eta_text(item)
        if estimate:
            lines.append(estimate)
        lines.append("")
    location = map_line(state)
    if location:
        lines.extend([location, ""])
    checked = state.get("lastChecked")
    try:
        checked_text = datetime.fromisoformat(checked).astimezone(TZ).strftime("%d.%m.%Y %H:%M") if checked else datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        checked_text = str(checked)
    lines.append(f"🕒 Son kontrol: {checked_text}")
    return "\n".join(lines).strip()


def change_title(item):
    if not item.get("_changed"):
        return None
    previous_state = item.get("_previousState")
    current_state = bool(item.get("confirmedState", False))
    raw_state = bool(item.get("rawState", False))
    state_changed = previous_state is not None and previous_state != current_state
    previous_band = item.get("_previousBand")
    confirmed_band = item.get("confirmedBand")
    previous_level = clamp(item.get("_previousLevel"))
    current_level = clamp(item.get("filteredLevel", item.get("level", 0)))

    if confirmed_band == "empty" and previous_level >= 80 and current_level <= 20:
        return "✅ BOŞALTILDI"
    if state_changed and not current_state:
        return "❌ UYGUN DEĞİL"
    if state_changed and current_state and raw_state and confirmed_band in {"empty", "available"} and current_level <= 40:
        return "✅ TEKRAR UYGUN"
    if confirmed_band == "nearly_full" and previous_band != "nearly_full" and 80 <= current_level <= 89:
        return "⚠️ NEREDEYSE DOLU"
    if confirmed_band == "critical" and previous_band != "critical" and current_level >= 90:
        return "🚨 DOLULUK KRİTİK"
    return None


def alert(state):
    bins = state.get("bins") or {}
    changes = {kind: change_title(item) for kind, item in bins.items()}
    changes = {kind: title for kind, title in changes.items() if title}
    if not changes:
        return None

    details = []
    order = [kind for kind in ("pet", "glass", "aluminum", "can") if kind in bins]
    order += [kind for kind in bins if kind not in order]
    for kind in order:
        item = bins[kind]
        current_level = clamp(item.get("filteredLevel", item.get("level", 0)))
        title = changes.get(kind)
        if title:
            previous_level = clamp(item.get("_previousLevel"))
            details.extend([
                f"🔔 {bin_label(kind)} · {title}",
                f"Önce  {make_bar(previous_level)}  %{previous_level}",
                f"Şimdi {make_bar(current_level)}  %{current_level}",
                f"Durum: {suitability_text(item)}",
                "",
            ])
        else:
            details.extend([
                bin_label(kind),
                make_bar(current_level),
                f"%{current_level} · {suitability_text(item)}",
                "",
            ])

    location = map_line(state)
    if location:
        details.extend([location, ""])
    event = "✅ MAKİNE BOŞALTILDI" if state.get("simultaneousEmptying") else "🔔 DOA DURUM DEĞİŞİKLİĞİ"
    return "\n".join([
        event,
        heading(state),
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"🚚 Operasyon önceliği: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
        *details,
        f"🕒 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}",
    ]).strip()
