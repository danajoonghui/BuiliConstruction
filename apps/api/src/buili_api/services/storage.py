from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import mimetypes
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import boto3

from ..core.config import Settings
from ..core.errors import AppError


@dataclass(slots=True)
class ObjectInfo:
    size: int
    sha256: str | None = None
    content_type: str | None = None


class ObjectStorage:
    async def create_upload_url(self, object_key: str, content_type: str, expires: int, checksum_sha256: str | None = None) -> str:
        raise NotImplementedError

    async def put_bytes(self, object_key: str, data: bytes, content_type: str) -> ObjectInfo:
        raise NotImplementedError

    async def put_file(self, object_key: str, source: Path, content_type: str) -> ObjectInfo:
        return await self.put_bytes(object_key, await asyncio.to_thread(source.read_bytes), content_type)

    async def read_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError

    async def stat(self, object_key: str) -> ObjectInfo:
        raise NotImplementedError

    async def create_download_url(self, object_key: str, expires: int = 300) -> str:
        raise NotImplementedError


def safe_object_key(value: str) -> str:
    normalized = str(PurePosixPath(value.replace("\\", "/")))
    if normalized.startswith("/") or normalized == "." or ".." in PurePosixPath(normalized).parts:
        raise AppError(400, "INVALID_OBJECT_KEY", "Object storage key is invalid")
    return normalized


class LocalObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.storage_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, object_key: str) -> Path:
        path = (self.root / safe_object_key(object_key)).resolve()
        if self.root not in path.parents and path != self.root:
            raise AppError(400, "INVALID_OBJECT_KEY", "Object storage key escapes the storage root")
        return path

    async def create_upload_url(self, object_key: str, content_type: str, expires: int, checksum_sha256: str | None = None) -> str:
        del content_type, expires, checksum_sha256
        return f"{self.settings.public_api_url.rstrip('/')}/v1/uploads/by-key/{quote(safe_object_key(object_key), safe='')}/content"

    async def put_bytes(self, object_key: str, data: bytes, content_type: str) -> ObjectInfo:
        path = self.path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return ObjectInfo(size=len(data), sha256=hashlib.sha256(data).hexdigest(), content_type=content_type)

    async def put_file(self, object_key: str, source: Path, content_type: str) -> ObjectInfo:
        path = self.path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        await asyncio.to_thread(os.replace, source, path)
        return ObjectInfo(size=size, sha256=digest.hexdigest(), content_type=content_type)

    async def read_bytes(self, object_key: str) -> bytes:
        path = self.path_for(object_key)
        if not path.exists():
            raise AppError(404, "OBJECT_NOT_FOUND", "Stored object was not found")
        return await asyncio.to_thread(path.read_bytes)

    async def stat(self, object_key: str) -> ObjectInfo:
        path = self.path_for(object_key)
        if not path.exists():
            raise AppError(404, "OBJECT_NOT_FOUND", "Stored object was not found")
        data = await asyncio.to_thread(path.read_bytes)
        return ObjectInfo(
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            content_type=mimetypes.guess_type(path.name)[0],
        )

    async def create_download_url(self, object_key: str, expires: int = 300) -> str:
        del expires
        return f"{self.settings.public_api_url.rstrip('/')}/v1/files/{quote(safe_object_key(object_key), safe='')}"


class S3ObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket = settings.s3_bucket or ""
        self.client = boto3.client("s3", region_name=settings.s3_region, endpoint_url=settings.s3_endpoint_url)

    async def create_upload_url(self, object_key: str, content_type: str, expires: int, checksum_sha256: str | None = None) -> str:
        checksum = base64.b64encode(bytes.fromhex(checksum_sha256)).decode("ascii") if checksum_sha256 else None
        params = {"Bucket": self.bucket, "Key": safe_object_key(object_key), "ContentType": content_type}
        if checksum:
            params["ChecksumSHA256"] = checksum
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "put_object",
            Params=params,
            ExpiresIn=expires,
        )

    async def put_bytes(self, object_key: str, data: bytes, content_type: str) -> ObjectInfo:
        digest = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=safe_object_key(object_key),
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
            ChecksumSHA256=base64.b64encode(bytes.fromhex(digest)).decode("ascii"),
        )
        return ObjectInfo(size=len(data), sha256=digest, content_type=content_type)

    async def read_bytes(self, object_key: str) -> bytes:
        try:
            result = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=safe_object_key(object_key))
            return await asyncio.to_thread(result["Body"].read)
        except self.client.exceptions.NoSuchKey as exc:
            raise AppError(404, "OBJECT_NOT_FOUND", "Stored object was not found") from exc

    async def stat(self, object_key: str) -> ObjectInfo:
        try:
            result = await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=safe_object_key(object_key), ChecksumMode="ENABLED")
        except Exception as exc:
            raise AppError(404, "OBJECT_NOT_FOUND", "Stored object was not found") from exc
        return ObjectInfo(
            size=int(result["ContentLength"]),
            sha256=(
                base64.b64decode(result["ChecksumSHA256"]).hex()
                if result.get("ChecksumSHA256")
                else (result.get("Metadata") or {}).get("sha256")
            ),
            content_type=result.get("ContentType"),
        )

    async def create_download_url(self, object_key: str, expires: int = 300) -> str:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": safe_object_key(object_key),
                "ResponseContentDisposition": "attachment",
                "ResponseContentType": "application/octet-stream",
            },
            ExpiresIn=expires,
        )


def build_storage(settings: Settings) -> ObjectStorage:
    return S3ObjectStorage(settings) if settings.storage_backend == "s3" else LocalObjectStorage(settings)
