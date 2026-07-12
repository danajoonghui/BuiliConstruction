from __future__ import annotations

import asyncio

import boto3
import structlog

from ..core.config import Settings

logger = structlog.get_logger(__name__)


class EmailService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ses = boto3.client("ses", region_name=settings.s3_region) if settings.email_backend == "ses" else None

    @property
    def enabled(self) -> bool:
        return self.settings.email_backend != "disabled"

    async def send(self, *, to: str, subject: str, text: str) -> bool:
        if self.settings.email_backend == "disabled":
            return False
        if self.settings.email_backend == "log":
            await logger.ainfo("email.local_delivery", to=to, subject=subject, body=text)
            return True
        if not self.ses:
            return False
        # Production sender identity is intentionally environment-owned.
        sender = "BUILI <noreply@builiconstruction.com>"
        await asyncio.to_thread(
            self.ses.send_email,
            Source=sender,
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": text}}},
        )
        return True
