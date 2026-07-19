import re
from datetime import datetime
from zoneinfo import ZoneInfo

from status_manager import durumlari_yukle
from telegram import telegram_gonder, telegram_komutlarini_al

TZ = ZoneInfo("Europe/Istanbul")


def normalize(text):
    value = str(text or "").strip().lower()
    replacements = str.maketrans({"ğ": "g", "ü": "u", "ş": "s", "ı": "i", "ö": "o", "ç": "c"})
    value = value.translate(replacements)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def level_of(item):
    return int(item.get("filteredLevel", item.get("level", 0)) or 0)


def band_text(level):
    if level <= 20:
        return "✅ BOŞALTILMIŞ / ÇOK UYGUN"
    if level <= 40:
        return "✅ UYGUN"
    if level <= 79:
        return "🟡 DOLUYOR"
    if level <= 89:
        return "🟠 DOLMAK ÜZERE"
    return "🚨 KRİTİK / DOLUM SINIRINDA"


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


def bin_name(kind):
    return {
        "pet": "PET",
        "glass": "CAM",
        "aluminum": "ALÜMİNYUM",
        "can": "ALÜMİNYUM",
    }.get(kind, str(kind).upper())


def machine_card(state):
    lines = [f"📍 {state.get('name', 'Bilinmeyen Makine')}", ""]
    for kind, item in (state.get("bins") or {}).items():
        level = level_of(item)
        lines.extend([
            f"{bin_name(kind)} · %{level}",
            bar(level),
            band_text(level),
            "",
        ])
    checked = state.get("lastChecked")
    if checked:
        try:
            checked_dt = datetime.fromisoformat(checked).astimezone(TZ)
            checked_text = checked_dt.strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            checked_text = str(checked)
        lines.append(f"🕒 Son kontrol: {checked_text}")
    return "\n".join(lines).strip()


def resolve_region(command):
    value = normalize(command)
    if value in {"start", "help", "yardim", "komutlar", "menu"}:
        return "help"
    if value in {"durum", "tum", "tumu", "hepsi", "makineler"}:
        return "all"
    if "mugla merkez" in value or value in {"mugla", "merkez", "mentese"}:
        return "Muğla Merkez"
    if "ula" in value:
        return "Ula"
    if "yatagan" in value:
        return "Yatağan"
    if "milas" in value:
        return "Milas"
    return None


def help_text():
    return "\n".join([
        "♻️ DOA Takip Komutları",
        "",
        "Muğla Merkez — merkez makinelerinin son durumu",
        "Ula — Ula makinelerinin son durumu",
        "Yatağan — Yatağan makinesinin son durumu",
        "Milas — Milas makinesinin son durumu",
        "Durum — takip edilen bütün makineler",
        "",
        "Komutları / işareti olmadan da yazabilirsin.",
    ])


def send_region(states, region, chat_id):
    selected = []
    for state in states.values():
        if not isinstance(state, dict) or not state.get("bins"):
            continue
        if region == "all" or normalize(state.get("label")) == normalize(region):
            selected.append(state)

    if not selected:
        label = "takip edilen makineler" if region == "all" else region
        telegram_gonder(f"ℹ️ {label} için kayıtlı güncel makine bulunamadı.", chat_id)
        return

    selected.sort(key=lambda item: (0 if item.get("type") == "target" else 1, item.get("name", "")))
    title = "🎯 MUĞLA MERKEZ — GÜNCEL DURUM" if region == "Muğla Merkez" else "♻️ TÜM MAKİNELER — GÜNCEL DURUM" if region == "all" else f"♻️ {str(region).upper()} — GÜNCEL DURUM"
    telegram_gonder(f"{title}\n\n" + "\n\n────────────\n\n".join(machine_card(item) for item in selected), chat_id)


def telegram_komutlarini_isle():
    commands = telegram_komutlarini_al()
    if not commands:
        return

    states = durumlari_yukle()
    for command in commands:
        region = resolve_region(command["text"])
        if region == "help":
            telegram_gonder(help_text(), command["chat_id"])
        elif region:
            send_region(states, region, command["chat_id"])
        else:
            telegram_gonder("Komutu anlayamadım. Muğla Merkez, Ula, Yatağan, Milas veya Durum yazabilirsin.", command["chat_id"])
