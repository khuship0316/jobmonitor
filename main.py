import hashlib
import json
import os
import sys
import traceback

from searcher import check_firm_status
from notifier import send_alert

FIRMS_PATH = "firms.json"
STATE_PATH = "state.json"


def _key(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    firms = load_json(FIRMS_PATH, [])

state_exists = os.path.exists(STATE_PATH)
state = load_json(STATE_PATH, {})

# Treat a missing OR empty state file as the first run
first_run = not state_exists or not state
    

    new_postings = []
    unknowns = []
    errors = []

    for firm in firms:
        name = firm["name"]
        seen = set(state.get(name, []))
        try:
            result = check_firm_status(firm)
        except Exception as e:
            errors.append(f"{name}: {e}")
            traceback.print_exc()
            continue

        status = result.get("status")
        if status == "unknown":
            unknowns.append(f"{name}: {result.get('evidence', '')}")
            continue
        if status != "open":
            continue

        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        if not title and not url:
            continue

        k = _key(title, url)
        if k not in seen:
            seen.add(k)
            if not first_run:
                new_postings.append({
                    "firm": name,
                    "title": title or "(open, title not captured)",
                    "url": url,
                    "evidence": result.get("evidence", ""),
                })

        state[name] = list(seen)

    save_json(STATE_PATH, state)

    if first_run:
        print(f"First run: seeded baseline state for {len(firms)} firms, no alerts sent.")
    elif new_postings:
        print(f"Found {len(new_postings)} new posting(s), sending alert.")
        send_alert(new_postings)
    else:
        print("No new postings found.")

    if unknowns:
        print(f"\n{len(unknowns)} firm(s) came back 'unknown' (careers page not found via search):")
        for u in unknowns:
            print(f"  - {u}")

    if errors:
        print(f"\n{len(errors)} firm(s) failed (API/network error):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    sys.exit(main())
