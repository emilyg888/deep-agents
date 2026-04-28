from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from deep_agents.pipeline import PipelineRunner
from env_utils import load_project_dotenv


def _env_flag(name: str) -> bool:
    value = (sys.environ if hasattr(sys, "environ") else {}).get(name)
    if value is None:
        import os

        value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        dest="run_date",
        default=None,
        help="Optional YYYY-MM-DD date override for output naming.",
    )
    parser.add_argument(
        "--ignore-memory",
        action="store_true",
        help="Run the sample demo without reading or updating paper/theme memory.",
    )
    parser.add_argument(
        "--live-email",
        action="store_true",
        help="Send the generated email through SMTP in addition to writing the draft file.",
    )
    parser.add_argument(
        "--live-discord",
        action="store_true",
        help="Post the generated Discord message to the Weekflow webhook in addition to writing the draft file.",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent
    load_project_dotenv(root_dir / ".env")
    live_email = args.live_email or _env_flag("DEEP_AGENTS_LIVE_EMAIL")
    live_discord = args.live_discord or _env_flag("DEEP_AGENTS_LIVE_DISCORD")

    runner = PipelineRunner(root_dir=root_dir)
    used_on = date.fromisoformat(args.run_date) if args.run_date else None
    try:
        result = runner.run(
            used_on=used_on,
            respect_memory=not args.ignore_memory,
            send_live_email=live_email,
            send_live_discord=live_discord,
        )
    except ValueError as exc:
        print(f"Run rejected: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result.as_dict(), indent=2))
    print()
    print(result.post.body)
    print()
    print(f"Saved research note to: {result.storage_path}")
    if result.run_log_path:
        print(f"Saved run log to: {result.run_log_path}")
    for delivery in result.deliveries:
        action = "Sent" if delivery.sent else "Prepared"
        print(
            f"{action} {delivery.channel} delivery: {delivery.path} "
            f"[target={delivery.target} sent={delivery.sent} status={delivery.status}]"
        )


if __name__ == "__main__":
    main()
