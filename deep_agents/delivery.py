from __future__ import annotations

import importlib.util
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from .models import DeliveryArtifact, PaperSummary, Position, PostDraft, ThemeCandidate

DEFAULT_EMAIL_RECIPIENT = "emsyd888@gmail.com"
DEFAULT_DISCORD_CHANNEL = "Weekflow"
WEEKFLOW_CONFIG_PATH = Path("/Users/emilygao/LocalDocuments/Projects/Weekflow/config.py")


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    username: str
    password: str
    from_email: str


def _load_weekflow_webhook_url(config_path: Path) -> str | None:
    if not config_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("weekflow_config", config_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None

    keys = getattr(module, "API_KEYS", {})
    if not isinstance(keys, dict):
        return None
    webhook = keys.get("weekflow_discord_card_notify")
    return str(webhook) if webhook else None


def _load_smtp_settings() -> SMTPSettings | None:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")

    if host and port and username and password and from_email:
        return SMTPSettings(
            host=host,
            port=int(port),
            username=username,
            password=password,
            from_email=from_email,
        )

    gmail_sender = os.getenv("GMAIL_SENDER_EMAIL")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if gmail_sender and gmail_password:
        return SMTPSettings(
            host="smtp.gmail.com",
            port=587,
            username=gmail_sender,
            password=gmail_password,
            from_email=gmail_sender,
        )

    return None


def _reference_lines(theme: ThemeCandidate) -> list[str]:
    return [f"- [{paper.title}]({paper.url}) — {paper.source}" for paper in theme.supporting_papers]


def _build_email_text(
    *,
    recipient: str,
    lead_paper_summary: PaperSummary,
    theme: ThemeCandidate,
    position: Position,
    post: PostDraft,
) -> str:
    references = _reference_lines(theme)
    return "\n".join(
        [
            f"To: {recipient}",
            f"Subject: LinkedIn draft - {theme.theme}",
            "",
            f"Theme: {theme.theme}",
            "",
            "Lead paper summary:",
            f"- [{lead_paper_summary.title}]({lead_paper_summary.url}) — {lead_paper_summary.source}",
            f"- Authors: {', '.join(lead_paper_summary.authors)}",
            f"- Summary: {lead_paper_summary.summary}",
            "",
            "LinkedIn draft:",
            post.body,
            "",
            "Why it matters:",
            position.enterprise_implication,
            "",
            "Reference links:",
            *references,
        ]
    )


def _build_discord_text(
    *,
    channel: str,
    webhook_path: Path,
    webhook_configured: bool,
    lead_paper_summary: PaperSummary,
    theme: ThemeCandidate,
    post: PostDraft,
) -> str:
    references = _reference_lines(theme)
    webhook_status = "configured" if webhook_configured else "missing"
    return "\n".join(
        [
            f"Channel: {channel}",
            f"Weekflow webhook: {webhook_status} ({webhook_path})",
            "",
            f"**Theme:** {theme.theme}",
            "",
            "**Lead paper summary**",
            f"- [{lead_paper_summary.title}]({lead_paper_summary.url}) — {lead_paper_summary.source}",
            f"- Summary: {lead_paper_summary.summary}",
            "",
            "**LinkedIn draft**",
            post.body,
            "",
            "**Debate angle**",
            theme.why_debatable,
            "",
            "**Reference links**",
            *references,
        ]
    )


def _send_email(
    settings: SMTPSettings,
    *,
    recipient: str,
    subject: str,
    body: str,
) -> tuple[bool, str]:
    message = EmailMessage()
    message["From"] = settings.from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.host, settings.port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.username, settings.password)
        smtp.send_message(message)
    return True, "sent"


def _send_discord_message(webhook_url: str, content: str) -> tuple[bool, str]:
    payload = {"content": content[:1900]}
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "deep-agents/1.0 Discord Webhook Client",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return True, "sent"
            return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        return False, f"request failed: {reason}"


class DeliveryManager:
    def __init__(
        self,
        base_dir: Path,
        *,
        email_recipient: str = DEFAULT_EMAIL_RECIPIENT,
        discord_channel: str = DEFAULT_DISCORD_CHANNEL,
        weekflow_config_path: Path = WEEKFLOW_CONFIG_PATH,
    ) -> None:
        self.base_dir = base_dir
        self.email_recipient = email_recipient
        self.discord_channel = discord_channel
        self.weekflow_config_path = weekflow_config_path

    def deliver(
        self,
        *,
        used_on: date,
        lead_paper_summary: PaperSummary,
        theme: ThemeCandidate,
        position: Position,
        post: PostDraft,
        send_live_email: bool = False,
        send_live_discord: bool = False,
    ) -> list[DeliveryArtifact]:
        email_dir = self.base_dir / "email"
        discord_dir = self.base_dir / "discord"
        email_dir.mkdir(parents=True, exist_ok=True)
        discord_dir.mkdir(parents=True, exist_ok=True)

        email_text = _build_email_text(
            recipient=self.email_recipient,
            lead_paper_summary=lead_paper_summary,
            theme=theme,
            position=position,
            post=post,
        )
        email_path = email_dir / f"{used_on.isoformat()}-linkedin-draft.md"
        email_path.write_text(email_text, encoding="utf-8")

        webhook_url = _load_weekflow_webhook_url(self.weekflow_config_path)
        discord_text = _build_discord_text(
            channel=self.discord_channel,
            webhook_path=self.weekflow_config_path,
            webhook_configured=bool(webhook_url),
            lead_paper_summary=lead_paper_summary,
            theme=theme,
            post=post,
        )
        discord_path = discord_dir / f"{used_on.isoformat()}-linkedin-draft.md"
        discord_path.write_text(discord_text, encoding="utf-8")

        email_sent = False
        email_status = "draft only"
        if send_live_email:
            settings = _load_smtp_settings()
            if settings is None:
                email_status = (
                    "missing SMTP credentials; set SMTP_HOST/SMTP_PORT/SMTP_USERNAME/"
                    "SMTP_PASSWORD/SMTP_FROM_EMAIL or GMAIL_SENDER_EMAIL/GMAIL_APP_PASSWORD"
                )
            else:
                try:
                    email_sent, email_status = _send_email(
                        settings,
                        recipient=self.email_recipient,
                        subject=f"LinkedIn draft - {theme.theme}",
                        body=email_text,
                    )
                except Exception as exc:  # noqa: BLE001
                    email_sent = False
                    email_status = f"send failed: {exc}"

        discord_sent = False
        discord_status = "draft only"
        if send_live_discord:
            if not webhook_url:
                discord_status = "missing Weekflow webhook configuration"
            else:
                discord_sent, discord_status = _send_discord_message(webhook_url, discord_text)

        return [
            DeliveryArtifact(
                channel="email",
                path=str(email_path),
                preview=post.body[:120],
                target=self.email_recipient,
                sent=email_sent,
                status=email_status,
            ),
            DeliveryArtifact(
                channel="discord",
                path=str(discord_path),
                preview=post.body[:120],
                target=self.discord_channel,
                sent=discord_sent,
                status=discord_status,
            ),
        ]
