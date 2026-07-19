from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")


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


def alert(state):
    details = []
    for kind, item in (state.get("bins") or {}).items():
        if not item.get("_changed"):
            continue
        previous_state = item.get("_previousState")
        current_state = item.get("confirmedState", True)
        state_changed = previous_state is not None and previous_state != current_state
        important_band = item.get("confirmedBand") in {"empty", "nearly_full", "critical"}
        if not state_changed and not important_band:
            continue
        previous_level = clamp(item.get("_previousLevel"))
        current_level = clamp(item.get("filteredLevel", item.get("level", 0)))
        if item.get("confirmedBand") == "empty":
            title = "✅ BOŞALTILDI"
        elif not current_state:
            title = "❌ UYGUN DEĞİL"
        else:
            title = "✅ TEKRAR UYGUN"
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
