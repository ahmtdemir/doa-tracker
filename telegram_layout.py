from datetime import datetime
from zoneinfo import ZoneInfo

from alert_formatter import (
    change_title,
    confirmation_note,
    doa_suitability_text,
    live_level,
    ordered_bins,
    previous_level,
)

TZ = ZoneInfo("Europe/Istanbul")


def make_bar(level):
    level = max(0, min(100, int(round(float(level or 0)))))
    count = max(0, min(10, int(round(level / 10))))
    symbol = "🟩" if level <= 40 else "🟨" if level <= 79 else "🟧" if level <= 89 else "🟥"
    return symbol * count + "⬜" * (10 - count)


def bin_label(kind):
    return {"glass": "CAM", "pet": "PET", "aluminum": "ALÜMİNYUM", "can": "ALÜMİNYUM"}.get(kind, str(kind).upper())


def heading(state):
    region = state.get("label", "")
    if state.get("type") == "target":
        return f"🎯 MUĞLA MERKEZ HEDEFİ · {region}"
    return f"🚨 ERKEN UYARI · {str(region).upper()}"


def bin_block(kind, item):
    level = live_level(item)
    lines = [bin_label(kind), make_bar(level), f"%{level} · {doa_suitability_text(item).upper()}"]
    note = confirmation_note(item)
    if note:
        lines.append(note)
    return lines


def command_card(state):
    lines = [
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"🚚 Operasyon önceliği: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
    ]
    bins = state.get("bins") or {}
    for kind in ordered_bins(bins):
        lines.extend(bin_block(kind, bins[kind]))
        lines.append("")
    checked = state.get("lastChecked")
    if checked:
        try:
            checked = datetime.fromisoformat(checked).astimezone(TZ).strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            checked = str(checked)
        lines.append(f"🕒 Son kontrol: {checked}")
    return "\n".join(lines).strip()


def card(state):
    return "\n".join(["♻️ DOA MAKİNE DURUMU", heading(state), command_card(state)]).strip()


def alert(state):
    bins = state.get("bins") or {}
    changes = {kind: change_title(item) for kind, item in bins.items()}
    changes = {kind: title for kind, title in changes.items() if title}
    if not changes:
        return None

    details = []
    for kind in ordered_bins(bins):
        item = bins[kind]
        if kind in changes:
            before = previous_level(item)
            current = live_level(item)
            details.extend([
                f"🔔 {bin_label(kind)} · {changes[kind].upper()}",
                f"Önce  {make_bar(before)}  %{before}",
                f"Şimdi {make_bar(current)}  %{current}",
                f"Durum: {doa_suitability_text(item).upper()}",
            ])
            note = confirmation_note(item)
            if note:
                details.append(note)
        else:
            details.extend(bin_block(kind, item))
        details.append("")

    emptied = any("Boşaltıldı" in title or "BOŞALTILDI" in title for title in changes.values())
    event = "✅ MAKİNE BOŞALTILDI" if emptied else "🔔 DOA DURUM DEĞİŞİKLİĞİ"
    return "\n".join([
        event,
        heading(state),
        f"📍 {state.get('name', 'Bilinmeyen Makine')}",
        f"🚚 Operasyon önceliği: {state.get('operationPriority', 'DÜŞÜK')}",
        "",
        *details,
        f"🕒 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}",
    ]).strip()
