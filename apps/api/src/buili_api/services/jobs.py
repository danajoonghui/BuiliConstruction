from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import boto3
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import Settings
from ..db import SessionFactory
from ..models import Job

JobHandler = Callable[[AsyncSession, Job], Awaitable[dict[str, Any]]]
logger = structlog.get_logger(__name__)


class JobManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.handlers: dict[str, JobHandler] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.tasks: list[asyncio.Task] = []
        self.worker_engine = (
            create_async_engine(settings.worker_database_url, pool_pre_ping=True)
            if settings.worker_database_url
            else None
        )
        self.worker_session_factory = (
            async_sessionmaker(self.worker_engine, class_=AsyncSession, expire_on_commit=False)
            if self.worker_engine
            else None
        )
        self.sqs = (
            boto3.client("sqs", region_name=settings.s3_region, endpoint_url=settings.sqs_endpoint_url)
            if settings.job_backend == "sqs"
            else None
        )

    def register(self, kind: str, handler: JobHandler) -> None:
        self.handlers[kind] = handler

    async def start(self) -> None:
        if self.settings.job_backend == "local" and not self.tasks:
            self.tasks = [asyncio.create_task(self._worker(index), name=f"buili-worker-{index}") for index in range(self.settings.worker_concurrency)]

    async def consume_sqs_forever(self) -> None:
        if not self.sqs or not self.settings.sqs_queue_url:
            raise RuntimeError("SQS job backend is not configured")
        if self.settings.environment == "production" and self.worker_session_factory is None:
            raise RuntimeError("Production workers require a separate BUILI_WORKER_DATABASE_URL principal")
        while True:
            response = await asyncio.to_thread(
                self.sqs.receive_message,
                QueueUrl=self.settings.sqs_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=self.settings.job_visibility_timeout_seconds,
            )
            for message in response.get("Messages", []):
                heartbeat = asyncio.create_task(
                    self._extend_sqs_lease(message["ReceiptHandle"]),
                    name="buili-sqs-lease-heartbeat",
                )
                try:
                    payload = json.loads(message["Body"])
                    completed = await self._execute(str(payload["job_id"]))
                    if completed:
                        await asyncio.to_thread(
                            self.sqs.delete_message,
                            QueueUrl=self.settings.sqs_queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
                except Exception:
                    await logger.aexception("job.sqs_message_failed")
                finally:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)

    async def _extend_sqs_lease(self, receipt_handle: str) -> None:
        if not self.sqs or not self.settings.sqs_queue_url:
            return
        while True:
            await asyncio.sleep(self.settings.job_heartbeat_seconds)
            await asyncio.to_thread(
                self.sqs.change_message_visibility,
                QueueUrl=self.settings.sqs_queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=self.settings.job_visibility_timeout_seconds,
            )

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        if self.worker_engine:
            await self.worker_engine.dispose()

    async def enqueue(self, job_id: str) -> None:
        if self.sqs:
            await asyncio.to_thread(
                self.sqs.send_message,
                QueueUrl=self.settings.sqs_queue_url,
                MessageBody=json.dumps({"job_id": job_id}),
            )
        else:
            await self.queue.put(job_id)

    async def run_now(self, job_id: str) -> None:
        await self._execute(job_id)

    async def _worker(self, index: int) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self._execute(job_id)
            finally:
                self.queue.task_done()

    async def _execute(self, job_id: str) -> bool:
        factory = self.worker_session_factory or SessionFactory
        async with factory() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status not in {"queued", "retrying"}:
                return True
            handler = self.handlers.get(job.kind)
            if handler is None:
                job.status = "failed"
                job.error_json = {"code": "UNKNOWN_JOB_KIND", "message": f"No handler for {job.kind}"}
                await session.commit()
                return True
            job.status = "running"
            job.progress = 0.05
            job.attempts += 1
            await session.commit()
            try:
                output = await handler(session, job)
                job.status = "succeeded"
                job.progress = 1.0
                job.output_json = output
                job.error_json = {}
                await session.commit()
                await logger.ainfo("job.succeeded", job_id=job.id, kind=job.kind)
                return True
            except Exception as exc:
                await session.rollback()
                job = await session.get(Job, job_id)
                if job:
                    job.status = "retrying" if self.settings.job_backend == "sqs" else "failed"
                    job.error_json = {"code": type(exc).__name__, "message": str(exc)[:2000]}
                    await session.commit()
                await logger.aexception("job.failed", job_id=job_id, kind=job.kind)
                return self.settings.job_backend != "sqs"
