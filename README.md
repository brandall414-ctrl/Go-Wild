# GoWild tracker

Checks Frontier every hour and logs when a GoWild pass deal shows up or changes. Annual pass deals get `[ANNUAL PASS]` at the front of the alert. Email alerts are optional (see below); a Claude scheduled task also reads `state/runs.csv` and flags changes in Claude chats.

## What it watches

| Source | What it catches |
| --- | --- |
| [GoWild pass page](https://www.flyfrontier.com/deals/gowild-pass/) | The promo headline and any pass price or sale wording, like "Fall & Winter pass for $249" |
| [Frontier Miles terms](https://www.flyfrontier.com/frontiermiles/terms-and-conditions/) | Annual pass price lines, like "The renewal price for the 2026-2027 GoWild! Annual Pass is $699" |
| [Newsroom promotions feed](https://news.flyfrontier.com/tagfeed/en-us/tags/news,promotion) | New GoWild or pass press releases, which is where the big sales get announced |

Old promos that Frontier leaves hidden in the page code are ignored, and so are the per-flight fee lines in the FAQ.

## Set up email (optional, one time)

1. **Make a Gmail app password.** Go to your Google Account → Security → 2-Step Verification (it must be on) → App passwords. Name it "GoWild tracker" and copy the 16-character password.
2. **Add it to this repo.** On GitHub, open this repo → Settings → Secrets and variables → Actions → New repository secret. Add these:

   | Name | Value |
   | --- | --- |
   | `GMAIL_APP_PASSWORD` | the 16-character app password |
   | `GMAIL_ADDRESS` | the Gmail address that sends the alerts |
   | `ALERT_TO` | optional, a different address to receive alerts (defaults to `GMAIL_ADDRESS`) |

   Never put the password in a file in this repo.
3. **Send a test.** Actions tab → Watch GoWild → Run workflow → tick "Send a test email" → Run.

## What you'll get

- **First run:** a "Live and watching" email with the current offers.
- **When something changes:** an email with what's new, what's gone, and the link.
- **If it breaks:** a "Not working" email after 6 failed checks in a row, and "Working again" when it recovers.

Nothing is sent when nothing changes.

## Files

- `gowild/parse.py` pulls offer lines out of each page.
- `gowild/watch.py` compares them to the last run and sends the email.
- `state/seen.json` is what it saw last time. Delete it to reset.
- `state/runs.csv` is a log of every check (`time_utc,ok,note`; notes starting with `alert:` mean something changed).
- `.github/workflows/watch.yml` runs it every hour at 13 past. GitHub sometimes runs scheduled jobs late, so expect some checks to be delayed.
