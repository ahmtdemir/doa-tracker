from datetime import datetime
from zoneinfo import ZoneInfo

import scraper
from alert_formatter import alert, safe_apply_simultaneous_emptying, safe_confirm_boolean
from commands import telegram_komutlarini_isle

TZ = ZoneInfo("Europe/Istanbul")
OPEN_HOUR = 8
CLOSE_HOUR = 22

scraper.alert = alert
scraper.confirm_boolean = safe_confirm_boolean
scraper.apply_simultaneous_emptying = safe_apply_simultaneous_emptying

current_time = datetime.now(TZ)
print(f"DOA Tracker başladı: {current_time.strftime('%d.%m.%Y %H:%M')}")

if OPEN_HOUR <= current_time.hour < CLOSE_HOUR:
    scraper.siteyi_test_et()
    telegram_komutlarini_isle()
else:
    print("Gece modu aktif: sistem 22:00-08:00 arasında tarama ve Telegram bildirimi üretmez.")
