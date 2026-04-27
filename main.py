from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from deep_agents.pipeline import PipelineRunner
from env_utils import load_project_dotenv


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

    runner = PipelineRunner(root_dir=root_dir)
    used_on = date.fromisoformat(args.run_date) if args.run_date else None
    result = runner.run(
        used_on=used_on,
        respect_memory=not args.ignore_memory,
        send_live_email=args.live_email,
        send_live_discord=args.live_discord,
    )

    print(json.dumps(result.as_dict(), indent=2))
    print()
    print(result.post.body)
    print()
    print(f"Saved research note to: {result.storage_path}")
    for delivery in result.deliveries:
        print(
            f"Prepared {delivery.channel} delivery: {delivery.path} "
            f"[target={delivery.target} sent={delivery.sent} status={delivery.status}]"
        )


if __name__ == "__main__":
    main()
