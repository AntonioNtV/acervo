import uuid
from collections.abc import AsyncIterator
from typing import Any, BinaryIO

import aioboto3
from botocore.exceptions import ClientError

from acervo.core.settings import Settings

PART_SIZE = 5 * 1024 * 1024


def key_for(kb_id: uuid.UUID, sha256: str) -> str:
    """Files are stored under their content, so moving or renaming a node never touches the bucket."""
    return f"kb/{kb_id}/{sha256}"


class Storage:
    """The bucket where every file of every base is kept byte for byte."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bucket = settings.s3_bucket
        self._session = aioboto3.Session()

    def _client(self) -> Any:
        return self._session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            region_name="us-east-1",
        )

    async def put(self, key: str, source: BinaryIO, size: int) -> None:
        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return
            except ClientError as error:
                if error.response["Error"]["Code"] != "404":
                    raise
            source.seek(0)
            if size <= PART_SIZE:
                await s3.put_object(Bucket=self.bucket, Key=key, Body=source.read())
            else:
                await self._put_in_parts(s3, key, source)

    async def _put_in_parts(self, s3: Any, key: str, source: BinaryIO) -> None:
        """One part at a time, so an upload of any size holds one part in memory, never the whole file."""
        upload = await s3.create_multipart_upload(Bucket=self.bucket, Key=key)
        target = {"Bucket": self.bucket, "Key": key, "UploadId": upload["UploadId"]}
        parts: list[dict[str, Any]] = []
        try:
            while part := source.read(PART_SIZE):
                number = len(parts) + 1
                sent = await s3.upload_part(**target, PartNumber=number, Body=part)
                parts.append({"PartNumber": number, "ETag": sent["ETag"]})
            await s3.complete_multipart_upload(**target, MultipartUpload={"Parts": parts})
        except BaseException:
            await s3.abort_multipart_upload(**target)
            raise

    async def stream(
        self, key: str, byte_range: tuple[int, int] | None = None, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        """The stored bytes, or bytes `start` to `end` of them, both included, as in an HTTP `Range` header."""
        extra = {"Range": f"bytes={byte_range[0]}-{byte_range[1]}"} if byte_range else {}
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key, **extra)
            body = response["Body"]
            try:
                async for chunk in body.iter_chunks(chunk_size):
                    yield chunk
            finally:
                body.close()

    async def delete(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)
