#!/usr/bin/env python3
"""
Mama's Fish House reservation availability poller.
Queries SevenRooms public widget API and emails on new matching slots.
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import httpx

# ========== CONFIG — edit here to change criteria ==========
VENUE_SLUG = "mamasfishhouserestaurantinn"
START_DATE = "2026-05-10"   # YYYY-MM-DD
END_DATE = "2026-05-13"     # YYYY-MM-DD (inclusive)
PARTY_SIZES = [6, 7, 8]
MIN_HOUR_HST = 18           # 18 = 6 PM
TIME_SLOT_CENTER = "20:00"  # query centered at 8pm
HALO_SIZE = 16              # 15-min increments; 16 = ±4hr (covers 4pm–midnight)

API_URL = "https://www.sevenrooms.com/api-yoa/availability/widget/range"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
ALERT_TO = os.environ["ALERT_TO"]

STATE_FILE = Path(__file__).parent / "state.json"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_slots": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def date_range(start_iso, end_iso):
    start = datetime.strptime(start_iso, "%Y-%m-%d").date()
    end = datetime.strptime(end_iso, "%Y-%m-%d").date()
    d = start
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def fetch_availability(party_size, start_date_iso):
    """Query SevenRooms widget API for one date + party size."""
    dt = datetime.strptime(start_date_iso, "%Y-%m-%d")
    start_date_us = dt.strftime("%m-%d-%Y")  # SevenRooms uses MM-DD-YYYY

    params = {
        "venue": VENUE_SLUG,
        "time_slot": TIME_SLOT_CENTER,
        "party_size": party_size,
        "halo_size_interval": HALO_SIZE,
        "start_date": start_date_us,
        "num_days": 1,
        "channel": "SEVENROOMS_WIDGET",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://www.sevenrooms.com/reservations/{VENUE_SLUG}",
    }
    resp = httpx.get(API_URL, params=params, headers=headers, timeout=20.0)
    if resp.status_code != 200:
        # surface first 200 chars of body to logs for diagnosis
        snippet = resp.text[:200].replace("\n", " ")
        print(f"    [body snippet] {snippet}")
    resp.raise_for_status()
    return resp.json()


def parse_hour(time_str):
    try:
        if not time_str:
            return None
        if "T" in time_str:
            return int(time_str.split("T")[1].split(":")[0])
        if "AM" in time_str.upper() or "PM" in time_str.upper():
            return datetime.strptime(time_str.strip(), "%I:%M %p").hour
        return int(time_str.split(":")[0])
    except Exception:
        return None


def extract_slots(payload, party_size, date_iso):
    """Walk SevenRooms response, return list of matching slot dicts."""
    slots = []
    data = payload.get("data", payload)
    avail = data.get("availability") or {}

    if not avail:
        print(f"    [debug] no 'availability' key. top keys: {list(data.keys())[:8]}")
        return slots

    # Response may key by either MM-DD-YYYY or YYYY-MM-DD; try both
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    candidates = [date_iso, dt.strftime("%m-%d-%Y"), dt.strftime("%m/%d/%Y")]
    shifts = None
    for k in candidates:
        if k in avail:
            shifts = avail[k]
            break
    if shifts is None:
        # nothing for this date — normal when fully booked
        return slots

    if not isinstance(shifts, list):
        return slots

    for shift in shifts:
        if not isinstance(shift, dict):
            continue
        times = shift.get("times") or []
        shift_name = shift.get("shift_category") or shift.get("shift_persistent_id", "")

        for t in times:
            time_raw = (
                t.get("time_iso")
                or t.get("time")
                or t.get("display_time")
                or ""
            )
            if not time_raw:
                continue
            hour_24 = parse_hour(time_raw)
            if hour_24 is None or hour_24 < MIN_HOUR_HST:
                continue
            display = t.get("time") or time_raw
            if "T" in display:
                display = display.split("T")[1][:5]
            slots.append({
                "date": date_iso,
                "time": display,
                "party_size": party_size,
                "shift": shift_name,
            })
    return slots


def slot_key(slot):
    return f"{slot['date']}|{slot['time']}|{slot['party_size']}"


def send_alert(new_slots):
    lines = [
        "MAMA'S FISH HOUSE — NEW AVAILABILITY",
        "",
        f"{len(new_slots)} new slot(s) matching criteria.",
        "Criteria: May 10–13, 2026 | party 6–8 | after 6 PM HST",
        "",
        "Slots:",
    ]
    for s in sorted(new_slots, key=slot_key):
        lines.append(
            f"  • {s['date']} @ {s['time']} — party of {s['party_size']}"
            + (f" ({s['shift']})" if s['shift'] else "")
        )
    lines += [
        "",
        f"Book immediately: https://www.sevenrooms.com/reservations/{VENUE_SLUG}",
        "",
        "Speed matters — slots from cancellations can disappear in minutes.",
        "",
        f"Alert generated {datetime.utcnow().isoformat(timespec='seconds')}Z",
    ]
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"[MAMA'S] {len(new_slots)} slot(s) open — BOOK NOW"
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_TO
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    print(f"Alert email sent to {ALERT_TO}")


def main():
    print(f"=== Poll started {datetime.utcnow().isoformat(timespec='seconds')}Z ===")
    state = load_state()
    seen = set(state.get("seen_slots", []))

    all_current = []
    errors = []

    for party_size in PARTY_SIZES:
        for date_iso in date_range(START_DATE, END_DATE):
            try:
                payload = fetch_availability(party_size, date_iso)
                slots = extract_slots(payload, party_size, date_iso)
                print(f"party={party_size} date={date_iso}: {len(slots)} matching slot(s)")
                all_current.extend(slots)
            except httpx.HTTPStatusError as e:
                print(f"party={party_size} date={date_iso}: HTTP {e.response.status_code}")
                errors.append(f"HTTP {e.response.status_code} party={party_size} date={date_iso}")
            except Exception as e:
                print(f"party={party_size} date={date_iso}: ERROR {type(e).__name__}: {e}")
                errors.append(f"{type(e).__name__} party={party_size} date={date_iso}")

    current_keys = {slot_key(s) for s in all_current}
    new_keys = current_keys - seen
    new_slots = [s for s in all_current if slot_key(s) in new_keys]
    
    # TEST MODE — remove after verifying email works
    new_slots = [{"date": "2026-05-10", "time": "19:00", "party_size": 6, "shift": "TEST"}]
    if new_slots:
        print(f"** {len(new_slots)} NEW slot(s) — sending alert **")
        try:
            send_alert(new_slots)
        except Exception as e:
            print(f"FAILED to send alert: {type(e).__name__}: {e}")
            sys.exit(1)
    else:
        print("No new slots this run.")

    state["seen_slots"] = sorted(current_keys)
    state["last_run"] = datetime.utcnow().isoformat(timespec='seconds') + "Z"
    save_state(state)

    print(f"=== Done. Known: {len(current_keys)} | new: {len(new_slots)} | errors: {len(errors)} ===")

    if errors and not all_current:
        sys.exit(2)


if __name__ == "__main__":
    main()
