from datetime import datetime
from zoneinfo import ZoneInfo

import scraper
from alert_formatter import alert
from commands import telegram_komutlarini_isle

TZ = ZoneInfo("Europe/Istanbul")
OPEN_HOUR = 8
CLOSE_HOUR = 22

# Otomatik değişiklik bildirimleri ile durum kartları aynı görsel dili kullanır.
scraper.alert = alert

current_time = datetime.now(TZ)
print(f"DOA Tracker başladı: {current_time.strftime('%d.%m.%Y %H:%M')}")

if OPEN_HOUR <= current_time.hour < CLOSE_HOUR:
    scraper.siteyi_test_et()
    telegram_komutlarini_isle()
else:
    print("Gece modu aktif: sistem 22:00-08:00 arasında tarama ve Telegram bildirimi üretmez.")
