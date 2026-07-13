from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import struct
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..models import FixtureAsset
from .storage import ObjectStorage


FINAL_FAILURES = {"failed", "banned", "expired", "cancelled", "unknown"}


@dataclass(frozen=True, slots=True)
class GlbInspection:
    byte_size: int
    vertex_count: int
    face_count: int
    bounds: dict[str, list[float]]


def inspect_glb(data: bytes) -> GlbInspection:
    """Validate a provider GLB before it enters BUILI-owned storage."""

    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("Provider output is not a GLB 2.0 file")
    _, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if version != 2 or declared_length != len(data):
        raise ValueError("Provider GLB header length/version is invalid")
    json_length, json_type = struct.unpack_from("<I4s", data, 12)
    if json_type != b"JSON" or 20 + json_length > len(data):
        raise ValueError("Provider GLB JSON chunk is invalid")
    document = json.loads(data[20 : 20 + json_length].decode("utf-8"))
    accessors = document.get("accessors") or []
    vertex_count = 0
    face_count = 0
    minimum: list[float] | None = None
    maximum: list[float] | None = None
    for mesh in document.get("meshes") or []:
        for primitive in mesh.get("primitives") or []:
            attributes = primitive.get("attributes") or {}
            position_index = attributes.get("POSITION")
            if isinstance(position_index, int) and position_index < len(accessors):
                accessor = accessors[position_index]
                vertex_count += int(accessor.get("count") or 0)
                current_min = accessor.get("min")
                current_max = accessor.get("max")
                if isinstance(current_min, list) and isinstance(current_max, list):
                    minimum = (
                        [float(item) for item in current_min]
                        if minimum is None
                        else [min(a, float(b)) for a, b in zip(minimum, current_min)]
                    )
                    maximum = (
                        [float(item) for item in current_max]
                        if maximum is None
                        else [max(a, float(b)) for a, b in zip(maximum, current_max)]
                    )
            index_accessor = primitive.get("indices")
            if isinstance(index_accessor, int) and index_accessor < len(accessors):
                face_count += int(accessors[index_accessor].get("count") or 0) // 3
            elif isinstance(position_index, int) and position_index < len(accessors):
                face_count += int(accessors[position_index].get("count") or 0) // 3
    if vertex_count <= 0 or face_count <= 0:
        raise ValueError("Provider GLB does not contain reviewable triangle geometry")
    return GlbInspection(
        byte_size=len(data),
        vertex_count=vertex_count,
        face_count=face_count,
        bounds={"min": minimum or [0.0, 0.0, 0.0], "max": maximum or [0.0, 0.0, 0.0]},
    )


class TripoFixtureAssetService:
    def __init__(self, settings: Settings, storage: ObjectStorage):
        self.settings = settings
        self.storage = storage

    @property
    def enabled(self) -> bool:
        return bool(self.settings.tripo_enabled and self.settings.tripo_api_key)

    def _headers(self) -> dict[str, str]:
        if not self.enabled or self.settings.tripo_api_key is None:
            raise RuntimeError("Tripo fixture generation is not configured")
        return {
            "Authorization": f"Bearer {self.settings.tripo_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def _trusted_download_url(self, value: str) -> str:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not hostname:
            raise ValueError("Tripo output URL must be HTTPS")
        if not any(
            hostname == suffix or hostname.endswith(f".{suffix}")
            for suffix in self.settings.tripo_download_hosts
        ):
            raise ValueError("Tripo output URL uses an untrusted host")

        def resolve() -> list[str]:
            return sorted(
                {
                    str(item[4][0])
                    for item in socket.getaddrinfo(
                        hostname, parsed.port or 443, type=socket.SOCK_STREAM
                    )
                }
            )

        for address in await asyncio.to_thread(resolve):
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("Tripo output host resolved to a non-public address")
        return value

    async def _provider_json(
        self, client: httpx.AsyncClient, method: str, path: str, **kwargs
    ) -> tuple[dict, str | None]:
        response = await client.request(method, path, headers=self._headers(), **kwargs)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("code", -1)) != 0:
            raise RuntimeError(
                f"Tripo API error {payload.get('code')}: {payload.get('message', 'unknown error')}"
            )
        return payload.get("data") or {}, response.headers.get("X-Tripo-Trace-ID")

    async def _download(self, client: httpx.AsyncClient, value: str) -> bytes:
        current = await self._trusted_download_url(value)
        for _ in range(4):
            async with client.stream("GET", current, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("Tripo download redirect omitted its location")
                    current = await self._trusted_download_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(
                    marker in content_type
                    for marker in (
                        "model/gltf-binary",
                        "application/octet-stream",
                        "binary/octet-stream",
                    )
                ):
                    raise ValueError("Tripo output did not return a GLB-compatible content type")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.settings.tripo_max_asset_bytes:
                        raise ValueError("Tripo output exceeds the configured asset size limit")
                    chunks.append(chunk)
                return b"".join(chunks)
        raise RuntimeError("Tripo download exceeded the redirect limit")

    async def generate(self, session: AsyncSession, asset: FixtureAsset) -> dict:
        if not self.enabled:
            raise RuntimeError(
                "Set TRIPO_API_KEY and BUILI_TRIPO_ENABLED=true on the worker to generate assets"
            )
        timeout = httpx.Timeout(45.0, connect=15.0)
        async with httpx.AsyncClient(
            base_url=self.settings.tripo_api_base_url.rstrip("/") + "/", timeout=timeout
        ) as client:
            submitted, trace_id = await self._provider_json(
                client,
                "POST",
                "task",
                json={
                    "type": "text_to_model",
                    "model_version": self.settings.tripo_model_version,
                    "prompt": asset.prompt,
                    "negative_prompt": asset.negative_prompt,
                    "face_limit": int(asset.provider_json.get("face_limit", 6000)),
                    "texture": True,
                    "pbr": True,
                },
            )
            task_id = str(submitted["task_id"])
            asset.provider_task_id = task_id
            asset.status = "generating"
            asset.provider_json = {**asset.provider_json, "submit_trace_id": trace_id}
            await session.commit()

            deadline = time.monotonic() + self.settings.tripo_task_timeout_seconds
            task: dict = {}
            poll_trace_id: str | None = None
            while time.monotonic() < deadline:
                task, poll_trace_id = await self._provider_json(client, "GET", f"task/{task_id}")
                status = str(task.get("status", "unknown"))
                if status == "success":
                    break
                if status in FINAL_FAILURES:
                    raise RuntimeError(f"Tripo task finalized with status {status}")
                await asyncio.sleep(self.settings.tripo_poll_interval_seconds)
            else:
                raise TimeoutError("Tripo asset generation exceeded the configured timeout")

            output = task.get("output") or {}
            model_url = output.get("pbr_model") or output.get("model") or output.get("base_model")
            if not model_url:
                raise RuntimeError("Tripo task succeeded without a model URL")
            data = await self._download(client, str(model_url))

        inspection = inspect_glb(data)
        if inspection.face_count > 250_000:
            raise ValueError("Generated presentation asset exceeds the 250,000-face review limit")
        object_key = (
            f"org/{asset.organization_id}/project/{asset.project_id}/fixture-assets/"
            f"{asset.id}/source.glb"
        )
        stored = await self.storage.put_bytes(object_key, data, "model/gltf-binary")
        asset.status = "review_required"
        asset.glb_storage_key = object_key
        asset.sha256 = stored.sha256
        asset.byte_size = stored.size
        asset.face_count = inspection.face_count
        asset.bounds_json = inspection.bounds
        asset.preview_url = (
            str(output.get("rendered_image") or output.get("generated_image") or "") or None
        )
        asset.provider_json = {
            **asset.provider_json,
            "poll_trace_id": poll_trace_id,
            "vertex_count": inspection.vertex_count,
            "provider_progress": task.get("progress"),
            "output_copied_to_buili_storage": True,
        }
        return {
            "fixture_asset_id": asset.id,
            "status": asset.status,
            "storage_key": object_key,
            "sha256": asset.sha256,
            "face_count": asset.face_count,
            "bounds": asset.bounds_json,
        }
