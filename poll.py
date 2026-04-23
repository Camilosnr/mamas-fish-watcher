#!/usr/bin/env python3
"""
Mama's Fish House reservation availability poller.
Queries SevenRooms public widget API and emails on new matching slots.
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import httpx

# ========== CONFIG — edit here to change criteria ==========
VENUE_SLUG = "mamasfishhouserestaurantinn"
START_DATE = "2026-05-10"   # YYYY-MM-DD
END_DATE = "2026-05-13"     # YYYY-MM-DD (inclusive)
PARTY_SIZES = [6, 7, 8]
MIN_HOUR_HST = 18           # 18 = 6 PM, local restaurant time

# SevenRooms public widget endpoint
API_URL = "https://www.sevenrooms.com/api-yoa/availability/widget/range"

# Secrets from env (set in GitHub Actions → Settings → Secrets)
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


def fetch_availability(party_size):
    """Query SevenRooms widget API for date range + party size."""
    params = {
        "venue": VENUE_SLUG,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "party_size": party_size,
        "channel": "SEVENROOMS_WIDGET",
        "halo_size_interval": 0,
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
    resp.raise_for_status()
    return resp.json()


def parse_hour(time_str):
    """Return 24h hour int, or None if unparseable."""
    try:
        if "T" in time_str:
            # ISO format e.g. "2026-05-10T18:30:00"
            return int(time_str.split("T")[1].split(":")[0])
        if "AM" in time_str.upper() or "PM" in time_str.upper():
            dt = datetime.strptime(time_str.strip(), "%I:%M %p")
            return dt.hour
        # 24h plain e.g. "18:30"
        return int(time_str.split(":")[0])
    except Exception:
        return None


def extract_slots(payload, party_size):
    """Walk SevenRooms response, return list of matching slot dicts."""
    slots = []
    data = payload.get("data", payload)
    avail = data.get("availability") or {}

    if not avail:
        print(f"  [debug] no 'availability' key. top keys: {list(data.keys())[:8]}")
        return slots

    for day, day_slots in avail.items():
        if not isinstance(day_slots, list):
            continue
        for s in day_slots:
            time_raw = (
                s.get("time_iso")
                or s.get("time")
                or s.get("time_slot")
                or s.get("display_time")
                or ""
            )
            if not time_raw:
                continue
            hour_24 = parse_hour(time_raw)
            if hour_24 is None or hour_24 < MIN_HOUR_HST:
                continue
            # Human-readable time
            display = s.get("time") or time_raw
            if "T" in display:
                display = display.split("T")[1][:5]
            slots.append({
                "date": day,
                "time": display,
                "party_size": party_size,
                "shift": s.get("shift_category", "") or s.get("shift_persistent_id", ""),
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
        try:
            payload = fetch_availability(party_size)
            slots = extract_slots(payload, party_size)
            print(f"party_size={party_size}: {len(slots)} matching slot(s)")
            all_current.extend(slots)
        except httpx.HTTPStatusError as e:
            print(f"party_size={party_size}: HTTP {e.response.status_code}")
            errors.append(f"HTTP {e.response.status_code} for party {party_size}")
        except Exception as e:
            print(f"party_size={party_size}: ERROR {type(e).__name__}: {e}")
            errors.append(f"{type(e).__name__} for party {party_size}")

    current_keys = {slot_key(s) for s in all_current}
    new_keys = current_keys - seen
    new_slots = [s for s in all_current if slot_key(s) in new_keys]

    if new_slots:
        print(f"** {len(new_slots)} NEW slot(s) — sending alert **")
        try:
            send_alert(new_slots)
        except Exception as e:
            print(f"FAILED to send alert: {type(e).__name__}: {e}")
            sys.exit(1)
    else:
        print("No new slots this run.")

    # State: keep current slots so reappearances re-alert
    state["seen_slots"] = sorted(current_keys)
    state["last_run"] = datetime.utcnow().isoformat(timespec='seconds') + "Z"
    save_state(state)

    print(f"=== Done. Known: {len(current_keys)} | new: {len(new_slots)} | errors: {len(errors)} ===")

    # Exit non-zero only if every party_size failed (so GH Actions flags it)
    if errors and not all_current:
        sys.exit(2)


if __name__ == "__main__":
    main()
