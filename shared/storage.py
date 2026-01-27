"""
Shared S3/MinIO storage utilities.
"""
import uuid
from typing import Optional, BinaryIO

from django.conf import settings


class S3Storage:
    """S3/MinIO storage utility class."""

    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name or settings.AWS_STORAGE_BUCKET_NAME
        self._client = None

    @property
    def client(self):
        """Lazy load S3 client."""
        if self._client is None:
            import boto3
            self._client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
        return self._client

    def upload_file(
        self,
        file_obj: BinaryIO,
        key: str = None,
        content_type: str = None,
    ) -> str:
        """Upload file to S3 and return the key."""
        if key is None:
            key = f"uploads/{uuid.uuid4()}"

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        self.client.upload_fileobj(
            file_obj,
            self.bucket_name,
            key,
            ExtraArgs=extra_args,
        )
        return key

    def download_file(self, key: str) -> bytes:
        """Download file from S3."""
        import io
        buffer = io.BytesIO()
        self.client.download_fileobj(self.bucket_name, key, buffer)
        buffer.seek(0)
        return buffer.read()

    def delete_file(self, key: str) -> bool:
        """Delete file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object',
    ) -> str:
        """Generate a presigned URL for the object."""
        return self.client.generate_presigned_url(
            method,
            Params={'Bucket': self.bucket_name, 'Key': key},
            ExpiresIn=expiration,
        )

    def file_exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """List files in bucket with prefix."""
        response = self.client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        return [obj['Key'] for obj in response.get('Contents', [])]


# Default storage instance
default_storage = S3Storage()
