import asyncio
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

_s3_client = None


def get_s3_client():
    """Вернуть синглтон boto3 S3-клиента (настроен для S3-совместимого хранилища / MinIO)."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                s3={"addressing_style": "path"},  # необходимо для MinIO
                signature_version="s3v4",
            ),
            use_ssl=settings.S3_USE_SSL,
        )
    return _s3_client


async def ensure_bucket_exists(bucket_name: Optional[str] = None) -> None:
    """Убедиться, что бакет существует, создать при необходимости."""
    bucket = bucket_name or settings.S3_BUCKET
    client = get_s3_client()
    loop = asyncio.get_event_loop()

    def _check_and_create() -> None:
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                try:
                    client.create_bucket(Bucket=bucket)
                except ClientError as create_exc:
                    # ignore if another process created it concurrently
                    create_code = create_exc.response["Error"]["Code"]
                    if create_code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                        raise
            else:
                raise

    await loop.run_in_executor(None, _check_and_create)


async def upload_fileobj(
    file_obj,
    bucket: str,
    key: str,
    content_type: Optional[str] = None,
) -> str:
    """Загрузить файл в S3 и вернуть key объекта."""
    client = get_s3_client()
    loop = asyncio.get_event_loop()

    extra_args: dict = {}
    if content_type:
        extra_args["ContentType"] = content_type

    def _upload() -> None:
        client.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra_args or None)

    await loop.run_in_executor(None, _upload)
    return key


async def delete_file(bucket: str, key: str) -> None:
    """Удалить файл из S3."""
    client = get_s3_client()
    loop = asyncio.get_event_loop()

    def _delete() -> None:
        client.delete_object(Bucket=bucket, Key=key)

    await loop.run_in_executor(None, _delete)


async def get_presigned_url(
    bucket: str,
    key: str,
    expiration: int = 3600,
    http_method: str = "GET",
) -> str:
    """Сгенерировать presigned URL для доступа к объекту в S3."""
    client = get_s3_client()
    loop = asyncio.get_event_loop()

    def _generate() -> str:
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
            HttpMethod=http_method,
        )

    return await loop.run_in_executor(None, _generate)