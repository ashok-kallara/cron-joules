"""CLI entry point for Cron Joules."""

import argparse
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# Valid check hours in ET (7PM and 10PM)
CHECK_HOURS = {19: False, 22: True}  # hour -> is_followup


def cmd_check_battery(force: bool = False) -> None:
    """Determine the check type from current ET time and run the battery check."""
    from handlers.check_battery import run_battery_check

    now_et = datetime.now(tz=ET)
    current_hour = now_et.hour

    logger.info(f"Current time ET: {now_et.strftime('%Y-%m-%d %H:%M %Z')} (hour={current_hour})")

    if current_hour not in CHECK_HOURS:
        if not force:
            # The 4-trigger cron fires at both EST and EDT UTC offsets to cover DST.
            # When the "wrong" offset trigger fires, skip gracefully.
            logger.info(
                f"Hour {current_hour} ET is not a check time (expected 19 or 22); "
                "skipping — this is the inactive DST trigger"
            )
            return
        logger.info("--force flag set; bypassing schedule gate")

    is_followup = CHECK_HOURS.get(current_hour, False)
    logger.info(f"Running {'10PM follow-up' if is_followup else '7PM'} battery check")

    result = run_battery_check(is_followup=is_followup, force=force)
    logger.info(f"Battery check result: {result}")

    if result["status"] == "error":
        sys.exit(1)


def cmd_poll_telegram() -> None:
    """Fetch pending Telegram commands and respond to each."""
    from handlers.telegram_webhook import process_command
    from services.config_service import get_telegram_poll_offset, set_telegram_poll_offset
    from services.telegram_client import get_telegram_client

    client = get_telegram_client()

    last_offset = get_telegram_poll_offset()
    next_offset = last_offset + 1 if last_offset is not None else None

    updates = client.get_updates(offset=next_offset)

    if not updates:
        logger.info("No pending Telegram updates")
        return

    logger.info(f"Processing {len(updates)} Telegram update(s)")

    for update in updates:
        message = update.get("message", {})
        if not message:
            continue

        chat_id = str(message.get("chat", {}).get("id"))
        text = message.get("text", "").strip()
        message_id = message.get("message_id")

        if text and text.startswith("/"):
            logger.info(f"Processing command from {chat_id}: {text}")
            try:
                response_text = process_command(text)
                client.reply_to_message(response_text, chat_id, message_id)
            except Exception as e:
                logger.exception(f"Error processing command '{text}': {e}")

    last_update_id = updates[-1]["update_id"]
    set_telegram_poll_offset(last_update_id)
    logger.info(f"Processed updates up to update_id={last_update_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cron Joules – EV charging reminder")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check-battery", help="Run the scheduled battery check")
    check_parser.add_argument("--force", action="store_true", help="Bypass the time-of-day schedule gate")
    subparsers.add_parser("poll-telegram", help="Poll and respond to pending Telegram commands")

    args = parser.parse_args()

    if args.command == "check-battery":
        cmd_check_battery(force=getattr(args, "force", False))
    elif args.command == "poll-telegram":
        cmd_poll_telegram()


if __name__ == "__main__":
    main()
