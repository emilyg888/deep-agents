from __future__ import annotations

import argparse
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


def _section(title: str, lines: list[str]) -> str:
    divider = "=" * 72
    content = "\n".join(line for line in lines if line)
    return f"{divider}\n{title}\n{divider}\n{content}"


def _paper_summary_text(paper) -> str:
    abstract = " ".join(paper.abstract.split())
    first_sentence = abstract.split(". ", 1)[0].strip()
    return first_sentence if first_sentence.endswith(".") else f"{first_sentence}."


def _render_result_output(result) -> str:
    summary_lines = [
        f"Theme: {result.selected_theme.theme}",
        (
            f"Lead paper: {result.lead_paper_summary.title} "
            f"— {result.lead_paper_summary.source}"
        ),
    ]
    provenance = result.state.synthesis_provenance
    if provenance is not None:
        summary_lines.append(f"Synthesis engine: {provenance.engine_used}")
        if provenance.fallback_used:
            summary_lines.append(
                f"Fallback: yes (primary={provenance.primary_engine})"
            )
            if provenance.fallback_reason:
                reason_lines = provenance.fallback_reason.splitlines()
                summary_lines.append(f"Fallback reason: {reason_lines[0]}")
                for extra_reason in reason_lines[1:]:
                    summary_lines.append(f"  {extra_reason}")
        else:
            summary_lines.append("Fallback: no")
    summary_lines.extend(
        [
            f"Research note: {result.storage_path}",
            f"Run log: {result.run_log_path}" if result.run_log_path else "",
        ]
    )

    delivery_lines = []
    for delivery in result.deliveries:
        action = "sent" if delivery.sent else "prepared"
        delivery_lines.append(
            f"{delivery.channel}: {action} "
            f"[target={delivery.target} status={delivery.status}]"
        )
        delivery_lines.append(f"path: {delivery.path}")
        delivery_lines.append("")
    if delivery_lines and delivery_lines[-1] == "":
        delivery_lines.pop()

    top_paper_lines = []
    for index, paper in enumerate(result.top_papers, start=1):
        if top_paper_lines:
            top_paper_lines.extend(["", "-" * 72, ""])
        top_paper_lines.extend(
            [
                f"{index}. {paper.title}",
                f"Citation: {paper.url}",
                f"Source: {paper.source}",
                f"Summary: {_paper_summary_text(paper)}",
            ]
        )
    if not top_paper_lines:
        top_paper_lines = ["No ranked papers."]

    sections = [
        _section("Run Summary", summary_lines),
        _section("Top 5 Papers", top_paper_lines),
        _section("LinkedIn Draft", [result.post.body]),
        _section("Delivery", delivery_lines),
    ]
    return "\n\n".join(sections)


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

    print(_render_result_output(result))


if __name__ == "__main__":
    main()
