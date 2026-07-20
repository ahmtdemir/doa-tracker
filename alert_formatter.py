from datetime import datetime
from zoneinfo import ZoneInfo

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


def alert(state):
    details = []
    for kind, item in (state.get("bins") or {}).items():
        if not item.get("_changed"):
            continue

        previous_state = item.get("_previousState")
        current_state = bool(item.get("confirmedState", False))
        raw_state = bool(item.get("rawState", False))
        state_changed = previous_state is not None and previous_state != current_state
        confirmed_band = item.get("confirmedBand")
        previous_level = clamp(item.get("_previousLevel"))
        current_level = clamp(item.get("filteredLevel", item.get("level", 0)))

        is_emptying = confirmed_band == "empty" and previous_level >= 80 and current_level <= 20
        became_unsuitable = state_changed and not current_state
        became_suitable = state_changed and current_state and raw_state and confirmed_band in {"empty", "available"} and current_level <= 40
        became_critical = confirmed_band in {"nearly_full", "critical"}

        if is_emptying:
            title = "✅ BOŞALTILDI"
        elif became_unsuitable:
            title = "❌ UYGUN DEĞİL"
        elif became_suitable:
            title = "✅ TEKRAR UYGUN"
        elif became_critical:
            title = "⚠️ DOLULUK KRİTİK"
        else:
            continue

        details.extend([
            f"{bin_label(kind)} · {title}",
            f"Önce  {make_bar(previous_level)}  %{previous_level}",
            f"Şimdi {make_bar(current_level)}  %{current_level}",
            "",
        ])

    if not details:
        return None

    region = state.get("label", "")
    heading = f"🎯 MUĞLA MERKEZ HEDEFİ · {region}" if state.get("type") == "target" else f"🚨 ERKEN UYARI · {str(region).upper()}"
    event = "✅ MAKİNE BOŞALTILDI" if state.get("simultaneousEmptying") else "🔔 DOA DURUM DEĞİŞİKLİĞİ"
    return "\n".join([
        event,
        heading,
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"🚚 Operasyon önceliği: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
        *details,
        f"🕒 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}",
    ]).strip()
