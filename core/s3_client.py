"""
S3 Client - Handles all S3 operations for the FASHN system
"""

import os
import boto3
from botocore.exceptions import ClientError
import requests
from datetime import datetime
from typing import Optional


class S3Client:
    """S3 operations for FASHN image generation system"""

    def __init__(self):
        self.aws_access_key = os.environ["AWS_ACCESS_KEY_ID"]
        self.aws_secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]
        self.bucket_name = os.getenv("AWS_S3_BUCKET", "saleorme")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        self.client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )

    def _get_content_type(self, filename: str) -> str:
        """Determine content type from filename"""
        ext = filename.lower().split('.')[-1]
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp'
        }
        return content_types.get(ext, 'image/jpeg')

    def _get_public_url(self, s3_key: str) -> str:
        """Get public URL for S3 object"""
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

    def upload_file(self, local_path: str, folder: str, filename: Optional[str] = None) -> Optional[str]:
        """
        Upload a local file to S3

        Args:
            local_path: Path to local file
            folder: S3 folder path
            filename: Optional custom filename

        Returns:
            Public S3 URL or None if failed
        """
        if filename is None:
            filename = os.path.basename(local_path)

        s3_key = f"{folder}/{filename}"
        content_type = self._get_content_type(filename)

        try:
            self.client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            return self._get_public_url(s3_key)
        except ClientError as e:
            print(f"S3 upload error: {e}")
            return None

    def upload_from_url(self, image_url: str, folder: str, filename: str) -> Optional[str]:
        """
        Download image from URL and upload to S3

        Args:
            image_url: Source image URL
            folder: S3 folder path
            filename: Target filename

        Returns:
            Public S3 URL or None if failed
        """
        try:
            # Download image
            response = requests.get(image_url, timeout=60)
            response.raise_for_status()

            s3_key = f"{folder}/{filename}"
            content_type = self._get_content_type(filename)

            # Upload to S3 (bucket policy handles public access)
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=response.content,
                ContentType=content_type
            )

            return self._get_public_url(s3_key)

        except Exception as e:
            print(f"S3 upload from URL error: {e}")
            return None

    def list_folder(self, folder: str) -> list:
        """List all files in an S3 folder"""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=folder
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'url': self._get_public_url(obj['Key'])
                    })

            return files

        except ClientError as e:
            print(f"S3 list error: {e}")
            return []

    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            print(f"S3 delete error: {e}")
            return False

    def move_to_approved(self, s3_url: str) -> Optional[str]:
        """Move a file to the approved folder"""
        # Extract key from URL
        key = s3_url.replace(f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/", "")
        filename = key.split('/')[-1]
        new_key = f"fashn-api/approved/{filename}"

        try:
            # Copy to new location (bucket policy handles public access)
            self.client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': key},
                Key=new_key
            )
            # Delete original
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return self._get_public_url(new_key)
        except ClientError as e:
            print(f"S3 move error: {e}")
            return None

    def move_to_rejected(self, s3_url: str) -> Optional[str]:
        """Move a file to the rejected folder"""
        key = s3_url.replace(f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/", "")
        filename = key.split('/')[-1]
        new_key = f"fashn-api/rejected/{filename}"

        try:
            self.client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': key},
                Key=new_key
            )
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return self._get_public_url(new_key)
        except ClientError as e:
            print(f"S3 move error: {e}")
            return None
