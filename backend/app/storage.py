import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


@lru_cache
def _client(endpoint: str | None = None):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    bucket = get_settings().s3_bucket
    try:
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        _client().create_bucket(Bucket=bucket)


async def put(key: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(
        _client().put_object,
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def get(key: str) -> bytes:
    response = await asyncio.to_thread(
        _client().get_object, Bucket=get_settings().s3_bucket, Key=key
    )
    return response["Body"].read()


async def delete(key: str) -> None:
    await asyncio.to_thread(_client().delete_object, Bucket=get_settings().s3_bucket, Key=key)


def signed_url(key: str) -> str:
    """生成短时签名 URL。纯本地计算，不产生网络请求。"""
    settings = get_settings()
    return _client(settings.s3_public_endpoint or None).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_url_ttl,
    )
