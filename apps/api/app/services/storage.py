from __future__ import annotations

import abc
from pathlib import Path
from typing import BinaryIO, Union

from app.core.config import get_settings

settings = get_settings()

# Providers accept fully-buffered bytes or an open binary file-like object
# (e.g. a spooled temp file); httpx streams file-likes without buffering.
UploadData = Union[bytes, BinaryIO]


class StorageProvider(abc.ABC):
    @abc.abstractmethod
    async def upload(self, bucket: str, path: str, data: UploadData, content_type: str) -> str:
        """Upload file and return public URL."""

    @abc.abstractmethod
    async def delete(self, bucket: str, path: str) -> None:
        """Delete file from storage."""

    @abc.abstractmethod
    async def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Get a signed/download URL."""


class SupabaseStorage(StorageProvider):
    def __init__(self):
        import httpx
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError(
                "Supabase storage is not configured. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY in the API environment."
            )
        self.base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self.public_base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public"
        self.key = settings.supabase_service_role_key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

    async def upload(self, bucket: str, path: str, data: UploadData, content_type: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/object/{bucket}/{path}",
                headers={
                    **self.headers,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=data,
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Supabase storage upload failed ({resp.status_code}): {resp.text[:500]}"
                )
        return f"{self.public_base}/{bucket}/{path}"

    async def delete(self, bucket: str, path: str) -> None:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.base_url}/object/{bucket}/{path}",
                headers={**self.headers, "Authorization": f"Bearer {self.key}"},
            )
            resp.raise_for_status()

    async def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/object/sign/{bucket}/{path}",
                headers={**self.headers, "Authorization": f"Bearer {self.key}"},
                json={"expiresIn": expires_in},
            )
            resp.raise_for_status()
            signed_url = resp.json().get("signedURL") or resp.json().get("signedUrl")
            if signed_url.startswith("/"):
                signed_url = f"{self.base_url}{signed_url}"
            return signed_url


class AppwriteStorage(StorageProvider):
    def __init__(self):
        import httpx
        self.endpoint = settings.appwrite_endpoint
        self.project_id = settings.appwrite_project_id
        self.api_key = settings.appwrite_api_key
        self.bucket_id = settings.appwrite_storage_bucket_id
        self.headers = {
            "X-Appwrite-Project": self.project_id,
            "X-Appwrite-Key": self.api_key,
            "Content-Type": "multipart/form-data",
        }

    async def upload(self, bucket: str, path: str, data: UploadData, content_type: str) -> str:
        import httpx
        files = {"file": (Path(path).name, data, content_type)}
        data_fields = {"fileId": "unique()", "permissions[0]": 'read("any")'}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.endpoint}/storage/buckets/{self.bucket_id}/files",
                headers={k: v for k, v in self.headers.items() if k != "Content-Type"},
                data=data_fields,
                files=files,
            )
            resp.raise_for_status()
            file_id = resp.json()["$id"]
        return f"{self.endpoint}/storage/buckets/{self.bucket_id}/files/{file_id}/view?project={self.project_id}"

    async def delete(self, bucket: str, path: str) -> None:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.endpoint}/storage/buckets/{self.bucket_id}/files/{path}",
                headers={k: v for k, v in self.headers.items() if k != "Content-Type"},
            )
            if resp.status_code != 404:
                resp.raise_for_status()

    async def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.endpoint}/storage/buckets/{self.bucket_id}/files/{path}/view",
                headers={k: v for k, v in self.headers.items() if k != "Content-Type"},
            )
            return str(resp.url)


def get_storage() -> StorageProvider:
    if settings.storage_provider == "appwrite":
        return AppwriteStorage()
    return SupabaseStorage()
