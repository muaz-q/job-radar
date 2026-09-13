"""Check Telegram alerts end to end:  python -m app.telegram_setup   (from backend/)

1. Reads TELEGRAM_BOT_TOKEN from job-radar/.env.
2. If TELEGRAM_CHAT_ID is empty, finds it from the latest message you sent the bot and saves it to .env.
3. Sends a real test alert, formatted exactly like a scanner alert.

The token is never printed.
"""

import re
import sys

import httpx

from app.config import REPO_ROOT, get_config
from app.notifications import DeliveryError, TelegramChannel

ENV_FILE = REPO_ROOT / ".env"


class _Sample:
    """Minimal stand-in for a Notification row."""
    id = 0
    heading = "New AI/ML Internship"
    body = "Test alert from Job Radar\nIf you can read this, alerts work\nBengaluru\nJust discovered"
    url = "https://github.com/"


def find_chat_id(token: str) -> str | None:
    try:
        response = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
    except httpx.HTTPError as exc:
        sys.exit(f"Could not reach Telegram ({type(exc).__name__}). Check your internet connection.")
    if response.status_code == 401:
        sys.exit("Telegram rejected the token (401). Copy it again from @BotFather into .env.")
    if response.status_code != 200:
        sys.exit(f"Telegram getUpdates failed: HTTP {response.status_code}")
    chats = [u["message"]["chat"] for u in response.json().get("result", [])
             if isinstance(u.get("message"), dict) and u["message"].get("chat", {}).get("type") == "private"]
    return str(chats[-1]["id"]) if chats else None


def save_chat_id(chat_id: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8")
    if re.search(r"^TELEGRAM_CHAT_ID=.*$", text, flags=re.M):
        text = re.sub(r"^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={chat_id}", text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\nTELEGRAM_CHAT_ID={chat_id}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def main() -> None:
    config = get_config()
    token = config.telegram_bot_token.strip()
    if not token:
        sys.exit(f"TELEGRAM_BOT_TOKEN is empty. Paste your token after TELEGRAM_BOT_TOKEN= in {ENV_FILE}")
    if not re.fullmatch(r"\d+:[\w-]{30,}", token):
        sys.exit("TELEGRAM_BOT_TOKEN doesn't look like a bot token (expected digits:letters). Check for extra spaces or quotes.")

    chat_id = config.telegram_chat_id.strip()
    if not chat_id:
        chat_id = find_chat_id(token)
        if not chat_id:
            sys.exit("No messages found. Open your bot in Telegram, send it any message (e.g. 'hi'), then run this again.")
        save_chat_id(chat_id)
        print(f"Found your chat id ({chat_id}) and saved it to .env")

    try:
        TelegramChannel(token, chat_id).deliver([_Sample()])
    except DeliveryError as exc:
        sys.exit(f"Sending the test alert failed: {exc}")
    print("Test alert sent. Check Telegram.")
    print(f"For GitHub, add two repository secrets: TELEGRAM_BOT_TOKEN (the token) and TELEGRAM_CHAT_ID = {chat_id}")


if __name__ == "__main__":
    main()
