from datetime import datetime, timedelta
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
OPENING_STABILIZATION_MINUTES = 20
DAY_NAMES = (
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
)

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


def parse_schedule_time(value):
    if not value:
        return None
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(value), pattern).time()
        except ValueError:
            continue
    return None


def schedule_entry(state, moment):
    schedule = state.get("weeklySchedule") or []
    if not schedule:
        return None, None

    today_name = DAY_NAMES[moment.weekday()]
    previous_name = DAY_NAMES[(moment.weekday() - 1) % 7]
    today = next((item for item in schedule if item.get("day") == today_name), None)
    previous = next((item for item in schedule if item.get("day") == previous_name), None)
    return today, previous


def machine_window(state, moment=None):
    moment = moment or datetime.now(TZ)
    today, previous = schedule_entry(state, moment)
    if today is None and previous is None:
        return None

    current_time = moment.time().replace(tzinfo=None)

    if previous and previous.get("overnight"):
        previous_end = parse_schedule_time(previous.get("endTime"))
        if previous_end and current_time < previous_end:
            opened_at = datetime.combine(
                (moment - timedelta(days=1)).date(),
                parse_schedule_time(previous.get("startTime")),
                tzinfo=TZ,
            )
            closed_at = datetime.combine(moment.date(), previous_end, tzinfo=TZ)
            return opened_at, closed_at

    if not today:
        return None

    start = parse_schedule_time(today.get("startTime"))
    end = parse_schedule_time(today.get("endTime"))
    if not start or not end:
        return None

    overnight = bool(today.get("overnight")) or end <= start
    opened_at = datetime.combine(moment.date(), start, tzinfo=TZ)
    closed_at = datetime.combine(
        moment.date() + (timedelta(days=1) if overnight else timedelta()),
        end,
        tzinfo=TZ,
    )
    return opened_at, closed_at


def machine_is_open(state, moment=None):
    moment = moment or datetime.now(TZ)
    window = machine_window(state, moment)
    if window is None:
        return True
    opened_at, closed_at = window
    return opened_at <= moment < closed_at


def in_opening_stabilization(state, moment=None):
    moment = moment or datetime.now(TZ)
    window = machine_window(state, moment)
    if window is None:
        return False
    opened_at, closed_at = window
    return opened_at <= moment < min(
        opened_at + timedelta(minutes=OPENING_STABILIZATION_MINUTES),
        closed_at,
    )


def guarded_alert(state):
    current = datetime.now(TZ)
    if not machine_is_open(state, current):
        print(f"Makine kapalı; alarm gönderilmedi: {state.get('name')}")
        return None
    if in_opening_stabilization(state, current):
        print(f"Açılış stabilizasyonu aktif; alarm gönderilmedi: {state.get('name')}")
        return None

    warning = clarify_pending_suitability(alert(state))
    if warning:
        state["_pendingAlarmRecord"] = warning
    return warning


def is_out_of_service(state):
    return state.get("machineStatus") == 2 and state.get("status") == 4


def machine_status_message(state, out_of_service, moment):
    timestamp = moment.strftime("%d.%m.%Y %H:%M")
    if out_of_service:
        return (
            "🚫 MAKİNE KULLANIM DIŞI\n"
            f"📍 {state.get('label')} · {state.get('name')}\n"
            f"🕒 {timestamp}"
        )
    return (
        "✅ MAKİNE TEKRAR KULLANIMA AÇILDI\n"
        f"📍 {state.get('label')} · {state.get('name')}\n"
        f"🕒 {timestamp}"
    )


def build_state_with_machine_status(machine, rule, old=None):
    old = old or {}
    state = _original_build_state(machine, rule, old)
    state.pop("scheduleDebug", None)
    state["weeklySchedule"] = machine.get("weeklySchedule") or []

    current_time = datetime.now(TZ)
    current = is_out_of_service(state)
    previous = old.get("outOfService")
    if previous is None and old:
        previous = is_out_of_service(old)

    pending = old.get("pendingOutOfService")
    state["outOfService"] = current

    if old and previous != current:
        if machine_is_open(state, current_time):
            state["_machineStatusAlert"] = machine_status_message(
                state, current, current_time
            )
            pending = None
        else:
            pending = current
    elif machine_is_open(state, current_time) and pending is not None:
        if pending == current:
            state["_machineStatusAlert"] = machine_status_message(
                state, current, current_time
            )
        pending = None

    if pending is not None:
        state["pendingOutOfService"] = pending
    else:
        state.pop("pendingOutOfService", None)
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
scraper.siteyi_test_et()
commands.telegram_komutlarini_isle()
