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
from alert_formatter import alert, card, command_card, safe_apply_simultaneous_emptying

TZ = ZoneInfo("Europe/Istanbul")
OPEN_HOUR = 8
CLOSE_HOUR = 22
OPENING_STABILIZATION_MINUTES = 20

_original_gecmis_kaydi_ekle = scraper.gecmis_kaydi_ekle


def guarded_alert(state):
    current = datetime.now(TZ)
    if current.hour == OPEN_HOUR and current.minute < OPENING_STABILIZATION_MINUTES:
        print("Açılış stabilizasyonu aktif; alarm gönderilmedi.")
        return None

    warning = alert(state)
    if warning:
        state["_pendingAlarmRecord"] = warning
    return warning


def history_with_alarm_record(machine_id, state):
    warning = state.pop("_pendingAlarmRecord", None)
    if warning:
        alarm_kaydi_ekle(machine_id, state, warning)
    return _original_gecmis_kaydi_ekle(machine_id, state)


alert_formatter.change_title = change_title_with_alarm_memory
scraper.card = card
scraper.alert = guarded_alert
scraper.confirm_boolean = confirm_boolean_two_way
scraper.filtered_bin = use_alarm_memory(scraper.filtered_bin)
scraper.apply_simultaneous_emptying = safe_apply_simultaneous_emptying
scraper.gecmis_kaydi_ekle = history_with_alarm_record
commands.machine_card = command_card

current_time = datetime.now(TZ)
print(f"DOA Tracker başladı: {current_time.strftime('%d.%m.%Y %H:%M')}")

if OPEN_HOUR <= current_time.hour < CLOSE_HOUR:
    scraper.siteyi_test_et()
    commands.telegram_komutlarini_isle()
else:
    print("Gece modu aktif: sistem 22:00-08:00 arasında tarama ve Telegram bildirimi üretmez.")
