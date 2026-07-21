from datetime import datetime
from zoneinfo import ZoneInfo

import alert_formatter
import commands
import scraper
from alarm_history_manager import alarm_kaydi_ekle
from alarm_level_fix import (
    change_title_with_alarm_memory,
    confirm_boolean_two_way,
    use_alarm_memory,
)
from alert_formatter import alert, safe_apply_simultaneous_emptying

TZ = ZoneInfo("Europe/Istanbul")
OPEN_HOUR = 8
CLOSE_HOUR = 22
OPENING_STABILIZATION_MINUTES = 20

_original_gecmis_kaydi_ekle = scraper.gecmis_kaydi_ekle
_original_build_state = scraper.build_state


def clarify_pending_suitability(message):
    if not message:
        return message
    lines = message.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("⏳ Tekrar uygun doğrulaması:") and index > 0:
            lines[index - 1] = lines[index - 1].replace(
                "✅ UYGUN", "⏳ UYGUNLUK DEĞERLENDİRİLİYOR", 1
            )
    return "\n".join(lines)


def guarded_alert(state):
    current = datetime.now(TZ)
    if current.hour == OPEN_HOUR and current.minute < OPENING_STABILIZATION_MINUTES:
        print("Açılış stabilizasyonu aktif; alarm gönderilmedi.")
        return None

    warning = clarify_pending_suitability(alert(state))
    if warning:
        state["_pendingAlarmRecord"] = warning
    return warning


def is_out_of_service(state):
    return state.get("machineStatus") == 2 and state.get("status") == 4


def build_state_with_machine_status(machine, rule, old=None):
    old = old or {}
    state = _original_build_state(machine, rule, old)
    current = is_out_of_service(state)
    previous = old.get("outOfService")
    if previous is None and old:
        previous = is_out_of_service(old)

    state["outOfService"] = current
    if old and previous != current:
        timestamp = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
        if current:
            state["_machineStatusAlert"] = (
                "🚫 MAKİNE KULLANIM DIŞI\n"
                f"📍 {state.get('label')} · {state.get('name')}\n"
                f"🕒 {timestamp}"
            )
        else:
            state["_machineStatusAlert"] = (
                "✅ MAKİNE TEKRAR KULLANIMA AÇILDI\n"
                f"📍 {state.get('label')} · {state.get('name')}\n"
                f"🕒 {timestamp}"
            )
    return state


def history_with_alarm_record(machine_id, state):
    machine_status_warning = state.pop("_machineStatusAlert", None)
    if machine_status_warning:
        scraper.telegram_gonder(machine_status_warning)

    warning = state.pop("_pendingAlarmRecord", None)
    if warning:
        alarm_kaydi_ekle(machine_id, state, warning)
    return _original_gecmis_kaydi_ekle(machine_id, state)


alert_formatter.change_title = change_title_with_alarm_memory
scraper.alert = guarded_alert
scraper.confirm_boolean = confirm_boolean_two_way
scraper.filtered_bin = use_alarm_memory(scraper.filtered_bin)
scraper.apply_simultaneous_emptying = safe_apply_simultaneous_emptying
scraper.gecmis_kaydi_ekle = history_with_alarm_record
scraper.build_state = build_state_with_machine_status

current_time = datetime.now(TZ)
print(f"DOA Tracker başladı: {current_time.strftime('%d.%m.%Y %H:%M')}")

if OPEN_HOUR <= current_time.hour < CLOSE_HOUR:
    scraper.siteyi_test_et()
    commands.telegram_komutlarini_isle()
else:
    print("Gece modu aktif: sistem 22:00-08:00 arasında tarama ve Telegram bildirimi üretmez.")
