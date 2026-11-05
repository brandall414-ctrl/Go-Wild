"""Check Frontier's GoWild pages and email when an offer changes.

Run: python -m gowild.watch            (normal hourly check)
     python -m gowild.watch --test     (send a test email showing what it sees now)
"""

import json
import os
import smtplib
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from . import parse

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "seen.json"
LOG = ROOT / "state" / "runs.csv"
MOUNTAIN = ZoneInfo("America/Denver")

SOURCES = {
    "deals": "https://www.flyfrontier.com/deals/gowild-pass/",
    "terms": "https://www.flyfrontier.com/frontiermiles/terms-and-conditions/",
    "feed": "https://news.flyfrontier.com/tagfeed/en-us/tags/news,promotion",
}
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
FAIL_ALERT_AFTER = 6  # consecutive failed runs (about 6 hours) before emailing about it


def fetch(url: str) -> str:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"deals": [], "terms": [], "feed": [], "failures": 0, "initialized": False}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def log_run(ok: bool, note: str) -> None:
    new = not LOG.exists()
    with LOG.open("a") as f:
        if new:
            f.write("time_utc,ok,note\n")
        f.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')},{int(ok)},\"{note}\"\n")


def send_email(subject: str, body: str) -> None:
    user = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = os.environ.get("ALERT_TO", "").strip() or user
    if not user or not pw:
        print("Email not sent: GMAIL_ADDRESS or GMAIL_APP_PASSWORD secret is missing.")
        print(f"--- would have sent ---\n{subject}\n\n{body}")
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"Email sent to {to}: {subject}")


def snapshot() -> dict:
    return {
        "deals": parse.deals_offers(fetch(SOURCES["deals"])),
        "terms": parse.terms_prices(fetch(SOURCES["terms"])),
        "feed": parse.feed_items(fetch(SOURCES["feed"])),
    }


def is_annual(text: str) -> bool:
    return "annual" in text.lower()


def build_alert(old: dict, new: dict) -> tuple[str, str] | None:
    added_deals = [x for x in new["deals"] if x not in old["deals"]]
    removed_deals = [x for x in old["deals"] if x not in new["deals"]]
    added_terms = [x for x in new["terms"] if x not in old["terms"]]
    old_ids = {i["id"] for i in old["feed"]}
    added_posts = [i for i in new["feed"] if i["id"] not in old_ids]

    if not (added_deals or added_terms or added_posts):
        return None  # an offer disappearing alone is not worth an email

    parts = []
    if added_posts:
        parts.append("NEW FRONTIER ANNOUNCEMENT")
        for p in added_posts:
            parts.append(f"* {p['title']}\n  {p['link']}")
    if added_deals:
        parts.append(f"GOWILD PAGE CHANGED\n{SOURCES['deals']}\nNew:")
        parts += [f"* {x}" for x in added_deals]
        if removed_deals:
            parts.append("Gone:")
            parts += [f"* {x}" for x in removed_deals]
    if added_terms:
        parts.append(f"ANNUAL PASS PRICE TERMS CHANGED\n{SOURCES['terms']}")
        parts += [f"* {x}" for x in added_terms]

    everything = " ".join([p["title"] for p in added_posts] + added_deals + added_terms)
    headline = (added_posts[0]["title"] if added_posts else (added_deals or added_terms)[0])[:110]
    tag = "ANNUAL PASS" if is_annual(everything) else "GoWild"
    subject = f"[{tag}] {headline}"
    when = datetime.now(MOUNTAIN).strftime("%a %b %-d, %-I:%M %p")
    body = "\n\n".join(parts) + f"\n\nChecked {when} Mountain."
    return subject, body


def current_summary(snap: dict) -> str:
    lines = ["What the tracker sees on Frontier right now:", "", "GoWild page offers:"]
    lines += [f"* {x}" for x in snap["deals"]] or ["* (none found)"]
    lines += ["", "Annual pass prices in the terms:"]
    lines += [f"* {x}" for x in snap["terms"]] or ["* (none found)"]
    lines += ["", "Latest GoWild announcements:"]
    lines += [f"* {p['title']}\n  {p['link']}" for p in snap["feed"][:3]] or ["* (none found)"]
    lines += ["", "You'll get an email like this whenever any of it changes."]
    return "\n".join(lines)


def main() -> int:
    test = "--test" in sys.argv
    state = load_state()
    try:
        snap = snapshot()
        if not snap["deals"]:
            raise RuntimeError("GoWild page loaded but no offers were found (layout may have changed)")
    except Exception as e:  # noqa: BLE001
        state["failures"] = state.get("failures", 0) + 1
        print(f"Check failed ({state['failures']} in a row): {e}")
        if state["failures"] == FAIL_ALERT_AFTER:
            send_email(
                "[GoWild tracker] Not working",
                f"The tracker has failed {FAIL_ALERT_AFTER} runs in a row, so it may miss a sale.\n\nLast error: {e}",
            )
        save_state(state)
        log_run(False, str(e)[:200].replace('"', "'"))
        return 1

    if state.get("failures", 0) >= FAIL_ALERT_AFTER:
        send_email("[GoWild tracker] Working again", "The tracker is reading Frontier's pages again.")
    state["failures"] = 0

    if test or not state.get("initialized"):
        title = "[GoWild tracker] Test email" if test else "[GoWild tracker] Live and watching"
        send_email(title, current_summary(snap))
        note = "test email" if test else "first run"
    else:
        alert = build_alert(state, snap)
        if alert:
            send_email(*alert)
            note = "alert: " + alert[0]
        else:
            note = "no change"

    state.update(snap)
    state["initialized"] = True
    save_state(state)
    log_run(True, note[:200].replace('"', "'"))
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
