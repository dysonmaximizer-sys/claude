#!/usr/bin/env python3
"""
screenshot_inject.py

Fetches attachments from a published Zendesk article and injects screenshot
<img> blocks into the release email draft at marked positions.

Each <!-- SCREENSHOT:FileName --> comment in email_draft.html is replaced with
a full-width image table block if a matching Zendesk attachment is found.
If no match is found the marker is silently removed and the caption remains.

Usage:
    source ~/.zshrc
    python3 resources/screenshot_inject.py output/2026-04-release/

Requirements:
    ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN in environment.
    release_payload.json must contain zendesk_draft_article_id.
"""

import sys
import os
import json
import urllib.request
import base64
import re


# ---------------------------------------------------------------------------
# Zendesk helpers
# ---------------------------------------------------------------------------

def fetch_attachments(subdomain, email, token, article_id):
    """Return dict of {filename_without_extension: content_url}."""
    credentials = base64.b64encode(
        f"{email}/token:{token}".encode()
    ).decode()
    url = (
        f"https://{subdomain}.zendesk.com/api/v2/help_center"
        f"/articles/{article_id}/attachments.json"
    )
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {credentials}"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    attachments = {}
    for att in data.get("article_attachments", []):
        name = os.path.splitext(att["file_name"])[0]
        attachments[name] = att["content_url"]
    return attachments


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def img_table(url, name):
    """Return a full-width email-safe image table block."""
    return (
        '<table class="wrapper" role="module" data-type="image" border="0" '
        'cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">\n'
        "  <tbody>\n"
        "    <tr>\n"
        '      <td style="font-size:6px; line-height:10px; padding:8px 0px 2px 0px;" '
        'valign="top" align="center">\n'
        '        <img class="max-width" border="0" '
        'style="display:block; color:#000000; text-decoration:none; '
        'font-family:Helvetica, arial, sans-serif; font-size:16px; '
        'max-width:100% !important; width:100%; height:auto !important;" '
        f'width="600" alt="{name}" src="{url}">\n'
        "      </td>\n"
        "    </tr>\n"
        "  </tbody>\n"
        "</table>"
    )


def inject_screenshots(html, attachments):
    """
    Replace every <!-- SCREENSHOT:Name --> marker with an <img> table if a
    matching attachment exists, or remove the marker silently if not.
    """
    found = 0
    missing = []

    def replace(match):
        nonlocal found
        name = match.group(1).strip()
        if name in attachments:
            found += 1
            return img_table(attachments[name], name)
        else:
            missing.append(name)
            return ""  # remove marker, caption table below is preserved

    updated = re.sub(r"<!-- SCREENSHOT:([^>-][^>]*) -->", replace, html)
    return updated, found, missing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    release_dir = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "."

    # Load release payload
    payload_path = os.path.join(release_dir, "release_payload.json")
    with open(payload_path) as f:
        payload = json.load(f)

    article_id = payload.get("zendesk_draft_article_id")
    if not article_id:
        print("ERROR: zendesk_draft_article_id not found in release_payload.json")
        sys.exit(1)

    # Zendesk credentials from environment
    subdomain = os.environ["ZENDESK_SUBDOMAIN"]
    email     = os.environ["ZENDESK_EMAIL"]
    token     = os.environ["ZENDESK_API_TOKEN"]

    print(f"Fetching attachments for article {article_id}…")
    attachments = fetch_attachments(subdomain, email, token, article_id)
    print(f"Found {len(attachments)} attachment(s): {list(attachments.keys()) or 'none'}")

    # Read email draft
    email_path = os.path.join(release_dir, "email_draft.html")
    with open(email_path) as f:
        html = f.read()

    # Count markers present
    markers = re.findall(r"<!-- SCREENSHOT:([^>-][^>]*) -->", html)
    print(f"Screenshot markers in email: {len(markers)} — {markers}")

    # Inject
    updated, injected, missing = inject_screenshots(html, attachments)

    # Write back
    with open(email_path, "w") as f:
        f.write(updated)

    print(f"\nInjected:  {injected} screenshot(s)")
    if missing:
        print(f"Not found: {missing}")
        print("  → These markers were removed. Upload matching files to the Zendesk article and re-run.")
    else:
        print("All markers resolved.")
    print(f"\nUpdated: {email_path}")


if __name__ == "__main__":
    main()
