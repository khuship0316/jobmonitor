# Summer 2028 Consulting Job Monitor

Checks 23 consulting/econ-consulting firms' career pages a few times a day and
alerts you (email + optional SMS-gateway text) the moment a posting appears
whose text contains **both** "2028" and "summer" (literal match — no
title-matching, no special-casing of grad-year vs. internship-year phrasing).

## How it works

1. `main.py` runs on a schedule (GitHub Actions cron, 4x/day by default).
2. For each firm in `firms.json` (just a name + optional domain hint — no
   URLs to maintain), `searcher.py` calls Claude with the built-in
   **web_search** tool and asks it to go find that firm's own careers page
   and check: is there a currently-open posting whose text contains both
   "2028" and "summer"? The model does the searching, navigating, and
   judgment call itself each run — no fixed URL or JS-rendering config to
   keep in sync with each firm's site.
3. Claude returns a strict JSON verdict: `open` / `not_open` / `unknown`,
   plus the posting title, URL, and a one-line note on what it found.
4. New "open" results (not seen in `state.json` before) are emailed to you,
   and optionally forwarded to a carrier SMS-gateway address as a text.
5. `state.json` is committed back to the repo after each run so dedupe
   persists across runs (GitHub Actions runners are otherwise stateless).

**Trade-off vs. the URL-scraping version**: this is far less brittle — no
per-firm URL or "does this page need a headless browser" config to babysit,
and it self-corrects if a firm renames or restructures their portal. The
cost is that each check is a live search-augmented model call instead of a
cheap page diff, so it's a bit slower and a little more expensive per check
(still cheap at 4x/day — see Cost below), and it's trusting the model's
search results and judgment on "is this open" rather than a fixed rule
you can audit line by line. The `evidence` field in every alert exists so
you can quickly sanity-check each "open" call rather than blindly trusting it.

**First run is a baseline seed** — it records whatever's currently posted
without alerting, so you don't get 23 firms' worth of existing listings all
at once. Only postings that appear *after* the first run trigger an alert.

## Setup

1. **Create a GitHub repo** and push this folder to it.

2. **Get an Anthropic API key** at [console.anthropic.com](https://console.anthropic.com)
   (pay-as-you-go). Cost per check now includes web search + a Sonnet-tier
   call rather than a cheap Haiku classification, so budget more than the
   old scraping version — roughly $10-20/month at 4 checks/day × 23 firms,
   depending on how many searches Claude runs per firm per check. Watch your
   usage on the console for the first few days and drop the check frequency
   in the workflow file if it's running higher than expected.

3. **Set up an email sender.** Easiest is a Gmail account with an
   [App Password](https://myaccount.google.com/apppasswords) (needs 2FA
   enabled on the account first) — regular Gmail passwords won't work over SMTP.

4. **Add repo secrets** — Settings → Secrets and variables → Actions → New repository secret:
   - `ANTHROPIC_API_KEY`
   - `SMTP_HOST` (e.g. `smtp.gmail.com`)
   - `SMTP_PORT` (`587`)
   - `SMTP_USER` (your sending email address)
   - `SMTP_PASS` (the app password, not your real password)
   - `ALERT_EMAIL_TO` (where you want alerts sent — can be the same address)
   - `SMS_GATEWAY_TO` *(optional)* — your number `@` your carrier's gateway
     domain, e.g. `5551234567@vtext.com` (Verizon), `@txt.att.net` (AT&T),
     `@tmomail.net` (T-Mobile). Free, no API key needed, but delivery isn't
     guaranteed instantly — carriers sometimes delay or spam-filter these.

5. **Enable Actions** on the repo (Actions tab → enable). The workflow runs
   automatically on the built-in schedule; you can also trigger it manually
   from Actions → Job Monitor → Run workflow to do the baseline seed run
   right away instead of waiting for the next scheduled slot.

## Customizing

- **Check frequency**: edit the `cron` lines in
  `.github/workflows/monitor.yml`. Cron times are UTC. Lower frequency =
  lower cost.
- **Firm list**: edit `firms.json`. Each entry needs `name`, an optional
  `hint_domain` (steers search to the firm's real site instead of an
  aggregator), and optional `role_hints` (known program names, e.g.
  "Business Analyst Intern" — helps the model find the right page faster,
  but matching still isn't gated on an exact title match, per the "2028" +
  "summer" rule below). Currently covers 24 firms across MBB, big
  consulting, and econ/research consulting.
- **Cycle rollover handling**: the prompt explicitly tells the model that if
  it finds last cycle's (e.g. "2027") posting already closed, that's a
  signal to go check the firm's live page directly for whether a 2028
  version has since replaced it, rather than concluding nothing's open.
- **Matching rule**: intentionally literal (`"2028"` AND `"summer"` present
  in the posting, no title filtering) per your earlier call to favor false
  positives over missed postings. To tighten or loosen it, edit the
  `SYSTEM_PROMPT` in `searcher.py`.
- **Model**: `searcher.py` uses `claude-sonnet-5`. You could try dropping to
  a Haiku-tier model to cut cost, but search-plus-judgment tasks like "is
  this really open, on the firm's real site" tend to be more reliable on
  the stronger model — test before switching.

## ⚠️ Before you rely on this

I couldn't live-test this against a real API key from this sandboxed
environment, so before trusting it unattended:

- **Run it manually once via `workflow_dispatch`** after setup and read the
  Actions run log closely. Check that the `evidence` field for each firm
  actually makes sense (right firm, right domain, right posting) rather than
  the model guessing or landing on a stale/aggregator page.
- **Web search results can be wrong or incomplete.** The model might miss a
  posting that's open but poorly indexed, or occasionally misjudge "open" vs.
  "coming soon." This is a real trade-off vs. the old fixed-URL scraper,
  which was more mechanical but needed constant upkeep. Treat `unknown` and
  `not_open` results in the logs as things to spot-check yourself
  periodically, not proof nothing's posted.
- **Firms with `unknown` status** (careers page not found via search) are
  printed in the run log but don't error out the whole workflow — check the
  log occasionally for firms that keep coming back unknown and consider
  adding a more specific `hint_domain`.

## Local testing

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in real values
export $(cat .env | xargs)
python main.py
```
