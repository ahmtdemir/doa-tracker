ALERT_STEP = 10
RETURN_CONFIRM_COUNT = 2


def clamp(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def use_alarm_memory(original_filtered_bin):
    def wrapped(raw, old=None, checked_at=None):
        old = old or {}
        item = original_filtered_bin(raw, old, checked_at)
        item["_previousLevel"] = old.get("level", old.get("filteredLevel"))
        item["lastAlertLevel"] = old.get(
            "lastAlertLevel",
            old.get("level", old.get("filteredLevel", item.get("level", 0))),
        )
        return item

    return wrapped


def confirm_boolean_two_way(raw_value, old):
    raw_value = bool(raw_value)
    confirmed = old.get("confirmedState")
    candidate = old.get("stateCandidate")
    count = int(old.get("stateCandidateCount", 0) or 0)

    if confirmed is None:
        return raw_value, None, 0, False
    if raw_value == confirmed:
        return confirmed, None, 0, False

    count = count + 1 if candidate == raw_value else 1
    if count >= RETURN_CONFIRM_COUNT:
        return raw_value, None, 0, True
    return confirmed, raw_value, count, False


def change_title_with_alarm_memory(item):
    before = clamp(item.get("_previousLevel"))
    current = clamp(item.get("level", item.get("filteredLevel", 0)))
    drop = before - current
    previous_state = item.get("_previousState")
    confirmed_state = bool(item.get("confirmedState", False))
    state_changed = previous_state is not None and previous_state != confirmed_state
    reference = clamp(item.get("lastAlertLevel", before))

    title = None
    if item.get("_definiteEmptying") or (before >= 75 and current <= 25 and drop >= 50):
        title = "✅ BOŞALTILDI"
    elif before >= 70 and drop >= 40:
        title = "↘️ SERT SEVİYE DÜŞÜŞÜ"
    elif state_changed and not confirmed_state:
        title = "❌ UYGUN DEĞİL"
    elif state_changed and confirmed_state:
        title = "✅ TEKRAR UYGUN"
    elif before < 90 <= current:
        title = "🚨 DOLULUK KRİTİK"
    elif before < 80 <= current < 90:
        title = "⚠️ NEREDEYSE DOLU"
    elif abs(current - reference) >= ALERT_STEP:
        title = "SEVİYE DEĞİŞİMİ"

    if title:
        item["lastAlertLevel"] = current
    return title


# Geriye dönük uyumluluk: mevcut import adı çalışmaya devam etsin.
use_previous_raw_level = use_alarm_memory
