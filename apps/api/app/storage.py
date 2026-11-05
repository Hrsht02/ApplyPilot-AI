from functools import lru_cache
from pathlib import Path

import boto3

from app.config import settings


class StorageError(RuntimeError):
    pass


@lru_cache
def s3_client():
    if not settings.s3_bucket:
        raise StorageError("S3_BUCKET must be configured when STORAGE_BACKEND=s3")
    options = {"region_name": settings.s3_region}
    if settings.s3_endpoint_url:
        options["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id:
        options["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        options["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **options)


def _local_path(key: str) -> Path:
    root = Path(settings.local_storage_path).resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise StorageError("Invalid storage key")
    return path


def save_bytes(key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
    if settings.storage_backend == "s3":
        try:
            s3_client().put_object(
                Bucket=settings.s3_bucket, Key=key, Body=content, ContentType=content_type
            )
        except Exception as exc:
            raise StorageError("Object storage upload failed") from exc
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def read_bytes(key: str) -> bytes:
    if settings.storage_backend == "s3":
        try:
            response = s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError("Object storage download failed") from exc
    path = _local_path(key)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StorageError("Stored document could not be read") from exc
