from __future__ import annotations

import asyncio

from .core.config import get_settings
from .core.logging import configure_logging
from .main import build_services


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    services = build_services(settings)
    if settings.job_backend == "sqs":
        await services.jobs.consume_sqs_forever()
    else:
        await services.jobs.start()
        await services.jobs.queue.join()


if __name__ == "__main__":
    asyncio.run(run())
