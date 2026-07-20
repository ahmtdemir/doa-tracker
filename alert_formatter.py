from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
RETURN_CONFIRM_COUNT = 2
BIN_ORDER = ("glass", "pet", "aluminum", "can")


def clamp(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def make_bar(level):
    level = clamp(level)
    count = max(0, min(5, int(round(level / 20))))
    symbol = "🟩" if level <= 40 else "🟨" if level <= 79 else "🟧" if level <= 89 else "🟥"
    return symbol * count + "▫️" * (5 - count)


def bin_label(kind):
    return {"pet": "PET", "glass": "CAM", "aluminum": "ALÜMİNYUM", "can": "ALÜMİNYUM"}.get(kind, str(kind).upper())


def ordered_bins(bins):
    order = [kind for kind in BIN_ORDER if kind in bins]
    order += [kind for kind in bins if kind not in order]
    return order


def live_level(item):
    return clamp(item.get("level", item.get("filteredLevel", 0)))


def previous_level(item):
    return clamp(item.get("_previousLevel"))


def doa_suitability_text(item):
    return "✅ Uygun" if bool(item.get("rawState", item.get("confirmedState", False))) else "❌ Uygun değil"


def confirmation_note(item):
    raw_state = bool(item.get("rawState", False))
    confirmed_state = bool(item.get("confirmedState", False))
    if raw_state == confirmed_state:
        return None
    count = int(item.get("stateCandidateCount", 0) or 0)
    if raw_state:
        return f"⏳ Uygunluk doğrulanıyor: {count}/{RETURN_CONFIRM_COUNT}"
    return None


def map_line(state):
    return None


def eta_text(item):
    hours = item.get("estimatedHoursToFull")
    if hours is None:
        return None
    if hours < 1:
        return "Tahmini dolum: <1 saat"
    if hours < 24:
        return f"Tahmini dolum: ≈{hours:g} saat"
    return f"Tahmini dolum: ≈{hours / 24:.1f} gün"


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
    definitely_emptied = []
    for kind, item in state.get("bins", {}).items():
        previous = old_bins.get(kind, {})
        before = clamp(previous.get("level", previous.get("filteredLevel", 0)))
        current = live_level(item)
        if before >= 75 and current <= 25 and before - current >= 50:
            definitely_emptied.append(kind)
            item["_definiteEmptying"] = True
            item["_changed"] = True
            item["_previousLevel"] = before
            item["estimatedHoursToFull"] = None
    if not definitely_emptied:
        return False
    state["simultaneousEmptying"] = len(definitely_emptied) >= 2
    state["lastEmptiedAt"] = datetime.now(TZ).isoformat()
    return True


def heading(state):
    region = state.get("label", "")
    prefix = "HEDEF" if state.get("type") == "target" else "ERKEN UYARI"
    return f"{prefix} · {str(region).upper()}"


def bin_lines(kind, item, include_eta=True):
    level = live_level(item)
    lines = [f"{bin_label(kind)}  {make_bar(level)}  %{level} · {doa_suitability_text(item)}"]
    note = confirmation_note(item)
    if note:
        lines.append(note)
    if include_eta:
        estimate = eta_text(item)
        if estimate:
            lines.append(estimate)
    return lines


def command_card(state):
    lines = [
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"Öncelik: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
    ]
    bins = state.get("bins") or {}
    for kind in ordered_bins(bins):
        lines.extend(bin_lines(kind, bins[kind]))
    checked = state.get("lastChecked")
    if checked:
        try:
            checked_text = datetime.fromisoformat(checked).astimezone(TZ).strftime("%d.%m %H:%M")
        except (TypeError, ValueError):
            checked_text = str(checked)
        lines.extend(["", f"Son kontrol: {checked_text}"])
    return "\n".join(lines).strip()


def card(state):
    return "\n".join(["♻️ DOA DURUM", heading(state), command_card(state)]).strip()


def change_title(item):
    before = previous_level(item)
    current = live_level(item)
    drop = before - current
    previous_state = item.get("_previousState")
    confirmed_state = bool(item.get("confirmedState", False))
    state_changed = previous_state is not None and previous_state != confirmed_state

    if item.get("_definiteEmptying") or (before >= 75 and current <= 25 and drop >= 50):
        return "✅ Boşaltıldı"
    if before >= 70 and drop >= 40:
        return "↘️ Sert seviye düşüşü"
    if state_changed and not confirmed_state:
        return "❌ Uygun değil"
    if state_changed and confirmed_state:
        return "✅ Tekrar uygun"
    if before < 90 <= current:
        return "🚨 Doluluk kritik"
    if before < 80 <= current < 90:
        return "⚠️ Neredeyse dolu"
    return None


def alert(state):
    bins = state.get("bins") or {}
    changes = {kind: change_title(item) for kind, item in bins.items()}
    changes = {kind: title for kind, title in changes.items() if title}
    if not changes:
        return None

    details = []
    for kind in ordered_bins(bins):
        item = bins[kind]
        title = changes.get(kind)
        if title:
            before = previous_level(item)
            current = live_level(item)
            details.extend([
                f"{bin_label(kind)} · {title}",
                f"%{before} → %{current} · {doa_suitability_text(item)}",
            ])
            note = confirmation_note(item)
            if note:
                details.append(note)
        else:
            details.extend(bin_lines(kind, item, include_eta=False))

    event = "♻️ BOŞALTILMA" if any("Boşaltıldı" in title for title in changes.values()) else "🔔 DOA DEĞİŞİKLİĞİ"
    return "\n".join([
        event,
        heading(state),
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"Öncelik: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
        *details,
        "",
        datetime.now(TZ).strftime("%d.%m %H:%M"),
    ]).strip()
