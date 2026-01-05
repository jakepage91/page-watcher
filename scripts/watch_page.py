#!/usr/bin/env python3
"""
Page watcher with WhatsApp and Gmail notifications.
Monitors a web page for changes based on keywords or CSS selectors.
"""
import hashlib
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage

import requests
from bs4 import BeautifulSoup

STATE_PATH = "state/page_state.json"


def now_utc_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_state():
    """Load previous state from JSON file."""
    if not os.path.exists(STATE_PATH):
        return {"last_hash": None, "last_match": None, "last_checked": None}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load state: {e}", file=sys.stderr)
        return {"last_hash": None, "last_match": None, "last_checked": None}


def save_state(state):
    """Save current state to JSON file."""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def sha256(s: str) -> str:
    """Generate SHA-256 hash of a string."""
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def fetch(url: str, retries: int = 3) -> str:
    """
    Fetch a URL with retry logic.

    Args:
        url: URL to fetch
        retries: Number of retry attempts

    Returns:
        HTML content as string

    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PageWatcher/1.0; +https://github.com/)"
    }

    for attempt in range(retries):
        try:
            print(f"Fetching {url} (attempt {attempt + 1}/{retries})...")
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            print(f"✓ Fetched successfully ({len(r.text)} bytes)")
            return r.text
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"✗ Fetch failed: {e}. Retrying in {wait_time}s...", file=sys.stderr)
            time.sleep(wait_time)

    return ""  # Should never reach here


def extract_signal(html: str, selector: str | None, keywords: list[str] | None) -> tuple[str, str, dict]:
    """
    Extract the signal to monitor from HTML content.

    Args:
        html: HTML content
        selector: Optional CSS selector to target
        keywords: Optional list of keywords to look for

    Returns:
        Tuple of (signal_text, human_summary, metadata_dict)
        signal_text is hashed to detect changes
    """
    soup = BeautifulSoup(html, "lxml")

    # Option B: CSS selector-based (precise targeting)
    if selector:
        el = soup.select_one(selector)
        text = el.get_text(" ", strip=True) if el else ""
        summary = f"Selector '{selector}' matched: '{text[:150]}...'" if text else f"Selector '{selector}' not found"
        metadata = {"method": "selector", "selector": selector, "found": bool(text), "length": len(text)}
        return text, summary, metadata

    # Option A: Keyword-based (robust against page structure changes)
    page_text = soup.get_text(" ", strip=True)
    page_text_lower = page_text.lower()

    matches = []
    if keywords:
        for kw in keywords:
            kw_clean = kw.strip()
            if kw_clean and kw_clean.lower() in page_text_lower:
                matches.append(kw_clean)

    # Important: Use full page content as signal to detect ANY change
    # This prevents false negatives (missing real changes)
    # The matched keywords help us understand what triggered the alert
    signal = page_text

    summary = (
        f"Keywords matched: {matches if matches else 'none'} | "
        f"Page length: {len(page_text)} chars | "
        f"Keywords monitored: {len(keywords) if keywords else 0}"
    )

    metadata = {
        "method": "keywords",
        "total_keywords": len(keywords) if keywords else 0,
        "matched_keywords": matches,
        "page_length": len(page_text),
    }

    return signal, summary, metadata


def send_email(subject: str, body: str) -> bool:
    """
    Send email notification via SMTP.

    Returns:
        True if sent successfully, False otherwise
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    to = os.getenv("EMAIL_TO")
    from_addr = os.getenv("EMAIL_FROM") or user

    if not all([host, user, pwd, to, from_addr]):
        print("ℹ Email not configured (missing credentials)")
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.set_content(body)

        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)

        print(f"✓ Email sent to {to}")
        return True
    except Exception as e:
        print(f"✗ Email send failed: {e}", file=sys.stderr)
        return False


def send_whatsapp(subject: str, body: str) -> bool:
    """
    Send WhatsApp notification via Twilio API.

    Returns:
        True if sent successfully, False otherwise
    """
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    w_from = os.getenv("WHATSAPP_FROM")
    w_to = os.getenv("WHATSAPP_TO")

    if not all([sid, token, w_from, w_to]):
        print("ℹ WhatsApp not configured (missing Twilio credentials)")
        return False

    try:
        import base64

        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "From": w_from,
            "To": w_to,
            "Body": f"{subject}\n\n{body}",
        }
        headers = {
            "Authorization": f"Basic {auth}",
        }
        r = requests.post(url, data=data, headers=headers, timeout=30)
        r.raise_for_status()

        print(f"✓ WhatsApp sent to {w_to}")
        return True
    except Exception as e:
        print(f"✗ WhatsApp send failed: {e}", file=sys.stderr)
        return False


def send_notifications(url: str, state: dict, metadata: dict):
    """Send notifications via all configured channels."""
    matched = metadata.get("matched_keywords", [])

    subject = "🔔 Page Watcher Alert: Change Detected!"
    body = (
        f"The monitored page has changed!\n\n"
        f"URL: {url}\n"
        f"Time (UTC): {state['last_checked']}\n"
        f"Matched keywords: {', '.join(matched) if matched else 'N/A'}\n"
        f"Detection method: {metadata.get('method', 'unknown')}\n\n"
        f"The page content has been modified.\n\n"
        f"👉 Check the page now: {url}\n"
    )

    print("\n" + "=" * 60)
    print("🚨 CHANGE DETECTED!")
    print("=" * 60)
    print(body)
    print("=" * 60 + "\n")

    # Send via all configured channels
    email_sent = send_email(subject, body)
    whatsapp_sent = send_whatsapp(subject, body)

    if not email_sent and not whatsapp_sent:
        print("⚠ Warning: No notifications were sent (check your configuration)", file=sys.stderr)


def main():
    """Main entry point."""
    try:
        # Load configuration
        url = os.getenv("WATCH_URL")
        if not url:
            print("Error: WATCH_URL environment variable not set", file=sys.stderr)
            sys.exit(2)

        selector = os.getenv("WATCH_SELECTOR") or None
        keywords_raw = os.getenv("WATCH_KEYWORDS", "")
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] or None

        if not selector and not keywords:
            print("Error: Must provide either WATCH_SELECTOR or WATCH_KEYWORDS", file=sys.stderr)
            sys.exit(2)

        force_notify = os.getenv("FORCE_NOTIFY", "").lower() == "true"

        print(f"\n{'=' * 60}")
        print(f"Page Watcher - {now_utc_iso()}")
        print(f"{'=' * 60}")
        print(f"URL: {url}")
        print(f"Method: {'CSS selector' if selector else 'Keywords'}")
        if selector:
            print(f"Selector: {selector}")
        if keywords:
            print(f"Keywords: {', '.join(keywords)}")
        print(f"{'=' * 60}\n")

        # Handle test notification
        if force_notify:
            print("🧪 FORCE_NOTIFY enabled - sending test notification")
            test_state = {"last_checked": now_utc_iso()}
            test_metadata = {"method": "test", "matched_keywords": ["TEST"]}
            send_notifications(url, test_state, test_metadata)
            print("✓ Test notification sent")
            return

        # Load previous state
        state = load_state()

        # Fetch current page
        html = fetch(url)

        # Extract signal
        signal_text, summary, metadata = extract_signal(html, selector, keywords)
        current_hash = sha256(signal_text)

        # Update state
        state["last_checked"] = now_utc_iso()

        # Check if this is first run
        if state.get("last_hash") is None:
            state["last_hash"] = current_hash
            state["last_match"] = summary
            save_state(state)
            print("✓ Baseline established (first run)")
            print(f"  {summary}")
            return

        # Check for changes
        changed = (current_hash != state["last_hash"])

        if changed:
            # Page changed - send notifications
            send_notifications(url, state, metadata)

            # Update state after detecting change
            state["last_hash"] = current_hash
            state["last_match"] = summary
            save_state(state)
        else:
            # No change
            print("✓ No change detected")
            print(f"  {summary}")
            state["last_match"] = summary
            save_state(state)

    except requests.exceptions.RequestException as e:
        print(f"\n✗ Network error: {e}", file=sys.stderr)
        print("Will retry on next scheduled run", file=sys.stderr)
        # Exit gracefully so workflow doesn't fail
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
