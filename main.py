from datetime import datetime
from zoneinfo import ZoneInfo

import commands
import scraper
from alert_formatter import alert, card, map_line, safe_apply_simultaneous_emptying, safe_confirm_boolean

TZ = ZoneInfo("Europe/Istanbul")
OPEN_HOUR = 8
CLOSE_HOUR = 22
OPENING_STABILIZATION_MINUTES = 20


def guarded_alert(state):
    current = datetime.now(TZ)
    if current.hour == OPEN_HOUR and current.minute < OPENING_STABILIZATION_MINUTES:
        print("Açılış stabilizasyonu aktif; alarm gönderilmedi.")
        return None
    return alert(state)


base_command_card = commands.machine_card


def command_card_with_map(state):
    text = base_command_card(state)
    location = map_line(state)
    if location and location not in text:
        text = text + "\n\n" + location
    return text


scraper.card = card
scraper.alert = guarded_alert
scraper.confirm_boolean = safe_confirm_boolean
scraper.apply_simultaneous_emptying = safe_apply_simultaneous_emptying
commands.machine_card = command_card_with_map

current_time = datetime.now(TZ)
print(f"DOA Tracker başladı: {current_time.strftime('%d.%m.%Y %H:%M')}")

if OPEN_HOUR <= current_time.hour < CLOSE_HOUR:
    scraper.siteyi_test_et()
    commands.telegram_komutlarini_isle()
else:
    print("Gece modu aktif: sistem 22:00-08:00 arasında tarama ve Telegram bildirimi üretmez.")
