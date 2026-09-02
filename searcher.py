"""
For each firm, asks Claude (with the built-in web_search tool) to go find
the firm's own careers page and determine whether a Summer 2028 posting is
currently open - rather than us maintaining/scraping a fixed URL per firm.

This trades a bit of per-check cost and latency for much better robustness:
no per-firm URL/JS-rendering config to maintain, and the model can follow
redirects, site nav, and renamed portals on its own.
"""

import json
import os
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-5"  # search + judgment task benefits from the stronger model
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are checking whether a specific firm currently has an OPEN application \
for a Summer 2028 internship/analyst/associate program (any early-career program name counts \
- "Summer Associate," "Business Analyst Intern," "Summer Scholar," etc. - the exact program \
title does not matter for whether it qualifies).

You will be given the firm's own known program name(s) as a hint of what to search for on their \
site - use these as a starting point to find the right page faster, but do NOT require an exact \
title match. Firms sometimes rename or slightly reword their program between cycles.

Use web search to find the firm's OWN official careers/student-recruiting page (not a job \
aggregator like LinkedIn/Indeed/Handshake - go to the firm's own domain). Look for a live, \
currently-open posting whose own text contains BOTH:
  1. the literal string "2028" (e.g. "Summer 2028," "Class of 2028," "graduating 2028")
  2. the word "summer" (case-insensitive)
Apply this literally - do not infer "2028" from context like "rising senior" without the \
digits actually appearing on the page, and do not require the year and "summer" to be in the \
exact same sentence, just both present in the same posting's text.

IMPORTANT - checking for a rolled-over cycle: many of these firms run the same program every \
year and simply retire the previous cycle's posting/link when a new one opens, rather than \
posting a brand-new page from scratch. If your search turns up the firm's page for this program \
from the PREVIOUS cycle (e.g. a "2027" version) and it is now closed/expired, do NOT stop there \
and conclude "not_open." Treat a closed prior-cycle posting as a specific signal to dig further: \
go back to the firm's live careers/student page directly (not the stale search result) and check \
whether a 2028 version has since replaced it, since that's exactly the pattern you're watching for.

A posting only counts if you can confirm, from what you found, that applications appear \
CURRENTLY OPEN (not "coming soon," not a closed/expired posting, not a past cycle's page \
still indexed).

After searching, respond with ONLY a JSON object (no prose, no markdown fences):
{
  "status": "open" | "not_open" | "unknown",
  "title": "<posting title if status is open, else empty string>",
  "url": "<direct URL to the posting/application, else empty string>",
  "evidence": "<one short sentence on what you found and why, for a human to sanity-check>"
}

Use "unknown" only if you could not find the firm's careers page at all after searching. \
Use "not_open" if you found their careers page and, per the rollover check above, confirmed \
there is no 2028 posting live yet (even if a prior-cycle posting exists but is closed).
"""


def check_firm_status(firm: dict) -> dict:
    domain_hint = f" Their official domain is roughly {firm['hint_domain']}." if firm.get("hint_domain") else ""
    roles = firm.get("role_hints") or []
    role_hint = ""
    if roles:
        role_hint = f" Their known program name(s) for this: {', '.join(roles)}."

    user_content = (
        f"Firm: {firm['name']}.{domain_hint}{role_hint}\n\n"
        f"Search for and check whether {firm['name']} currently has an open Summer 2028 "
        f"internship/analyst/associate application, per the rule in your instructions - "
        f"including checking whether a 2028 posting has replaced an already-closed 2027 one."
    )

    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Concatenate all text blocks; the final one should be the JSON verdict
    # (earlier text blocks, if any, are the model's interleaved reasoning
    # between search calls).
    text_blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    if not text_blocks:
        return {"status": "unknown", "title": "", "url": "", "evidence": "No text response from model."}

    raw = text_blocks[-1].strip().replace("```json", "").replace("```", "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "unknown", "title": "", "url": "", "evidence": f"Unparseable response: {raw[:200]}"}

    result.setdefault("status", "unknown")
    result.setdefault("title", "")
    result.setdefault("url", "")
    result.setdefault("evidence", "")
    return result
