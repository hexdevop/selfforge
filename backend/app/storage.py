"""Object storage for progress photos: files go straight between the browser and storage.

The API never sees the bytes. It hands out short-lived presigned links — a POST form to
upload, a GET link to view — and keeps only the object key.
"""

import asyncio
from functools import cached_property
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class Storage:
    def __init__(self) -> None:
        self._bucket_ready = False

    def _client(self, endpoint: str) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            # Path-style: MinIO doesn't resolve bucket subdomains of localhost.
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @cached_property
    def internal(self) -> Any:
        return self._client(settings.S3_ENDPOINT_URL)

    @cached_property
    def public(self) -> Any:
        """Signs links for the host the browser uses; makes no requests itself."""
        return self._client(settings.S3_PUBLIC_URL)

    async def ensure_bucket(self) -> None:
        """Created on first use, so the API starts even when storage isn't up yet."""
        if self._bucket_ready:
            return
        bucket = settings.S3_PHOTOS_BUCKET

        def create() -> None:
            try:
                self.internal.head_bucket(Bucket=bucket)
            except ClientError:
                self.internal.create_bucket(Bucket=bucket)

        await asyncio.to_thread(create)
        self._bucket_ready = True

    def upload_form(self, key: str, content_type: str) -> dict[str, Any]:
        """A presigned POST: unlike PUT, its policy can cap the size and the type."""
        post: dict[str, Any] = self.public.generate_presigned_post(
            Bucket=settings.S3_PHOTOS_BUCKET,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["starts-with", "$Content-Type", "image/"],
                ["content-length-range", 1, settings.PHOTO_MAX_BYTES],
            ],
            ExpiresIn=settings.PHOTO_URL_TTL_SECONDS,
        )
        return post

    def view_url(self, key: str) -> str:
        url: str = self.public.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_PHOTOS_BUCKET, "Key": key},
            ExpiresIn=settings.PHOTO_URL_TTL_SECONDS,
        )
        return url

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self.internal.delete_object, Bucket=settings.S3_PHOTOS_BUCKET, Key=key
        )


storage = Storage()
